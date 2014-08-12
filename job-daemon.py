#!/opt/apps/python/2.7.3/bin/python
#
# Daemon for seq graph web frontend
#
# Copyright (C) The University of Edinburgh, 2013-2014. All Rights Reserved.

import os
import sys
import string
import MySQLdb
import time
import signal
import threading
import smtplib
from email.MIMEText import MIMEText
import urlparse
import traceback
import subprocess
import glob
from optparse import OptionParser
import warnings
import json
import shutil

dbHost = None
dbUser = None
dbPass = None
dbName = None

def loadDbSettings():
    try:
        dbSettingsFile = open('dbSettings.json')
        dbSettingsData = json.load(dbSettingsFile)
        global dbHost
        global dbUser
        global dbPass
        global dbName
        dbHost = dbSettingsData['dbHost']
        dbUser = dbSettingsData['dbUser']
        dbPass = dbSettingsData['dbPass']
        dbName = dbSettingsData['dbName']
        dbSettingsFile.close()
    except:
        return False

    if dbHost == None or dbUser == None or dbPass == None or dbName == None:
        return False

    return True

dbSettingsTable = "settings"
dbJobsTable     = "jobs"
dbResultsTable  = "results"
dbInputsTable   = "inputs"

exitNow         = 0
activeJobs     = 0
activeThreads   = []

def executeSQLQuery(query):
    try:
        db = MySQLdb.connect(host = dbHost, user = dbUser, passwd = dbPass, db = dbName)

        cursor = db.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        db.commit()

        db.close()
    except MySQLdb.Error, e:
        print "Query \"" + query + "\" failed to execute: \"" + e + "\""
        return None

    return result

def getSetting(key):
    """Retrieve a setting from the database"""

    result = executeSQLQuery("SELECT value FROM " + dbSettingsTable + " WHERE setting = '" + key + "'")

    if result != None:
        return result[0][0]
    else:
        return ""

def isNumber(string):
    """Test if a string is a number"""

    try:
        number = int(string)
    except ValueError:
        return False

    return True

class JobThread(threading.Thread):
    def __init__(self, jobId, lock):
        """Constructor for job thread"""

        threading.Thread.__init__(self)
        self.jobId  = jobId
        self.lock   = lock
        self.abort  = False

    def run(self):
        """Main thread functionality"""

        global activeJobs
        global activeThreads

        self.lock.acquire()
        activeThreads.append(self)
        self.lock.release()

        try:
            script = getSetting("script-file")

            result = executeSQLQuery("SELECT id, arguments, resultsDir FROM " + \
                    dbJobsTable + " WHERE id = '" + `int(self.jobId)` + "'")

            if len(result) == 1:
                row = result[0]
                jobId = row[0]
                arguments = row[1]
                resultsDir = row[2]

                scriptWithOptions = script + " " + arguments

                # Start script
                scriptProcess = subprocess.Popen(scriptWithOptions, shell=True, \
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                exitCode = scriptProcess.poll()

                while exitCode == None:
                    # Check for abort requests
                    if self.abort == False:
                        result = executeSQLQuery("SELECT abort FROM " + dbJobsTable + \
                                " WHERE id = '" + `int(jobId)` + "'")

                        if len(result) == 0 or result[0][0] != 0:
                            print "Aborting job " + `int(jobId)`
                            exitCode = 15
                            self.abort = True
                            scriptProcess.terminate()
                            break
                            
                    time.sleep(3)
                    exitCode = scriptProcess.poll()

                # Wait for script to complete
                out, err = scriptProcess.communicate()

                # Set finished time stamp
                executeSQLQuery("UPDATE " + dbJobsTable + " SET timefinished = '" + \
                    `int(time.time())` + "', exitcode = '" + `int(exitCode)` + \
                    "', output = '" + MySQLdb.escape_string(out) + \
                    "' WHERE id = '" + `int(jobId)` + "'")

                print "Finished job " + `int(jobId)`

                resultsDir = os.path.abspath(resultsDir)
                if os.path.exists(resultsDir):
                    print "Finding results in " + resultsDir
                    layoutFilenames = glob.glob(resultsDir + "/*.layout") + glob.glob(resultsDir + "/*.zip")

                    for layoutFilename in layoutFilenames:
                        print "...indexing " + layoutFilename
                        with open(layoutFilename, "rb") as layoutFile:
                            layoutFilebasename = os.path.basename(layoutFilename)
                            result = executeSQLQuery("INSERT INTO " + dbResultsTable + " (jobid, filename) " + \
                                    "VALUES('" + `int(jobId)` + "', '" + layoutFilebasename + "')")
                            if result == None:
                              break

            self.lock.acquire()
            activeThreads.remove(self)
            activeJobs = activeJobs - 1
            self.lock.release()
        except:
            print "Warning, unhandled exception in job thread"
            traceback.print_exc()

def startJob(jobId, lock):
    """Start a job"""

    global activeJobs

    print "Starting job " + `int(jobId)`

    result = executeSQLQuery("UPDATE " + dbJobsTable + " SET timestarted = '" + \
        `int(time.time())` + "' WHERE id = '" + `int(jobId)` + "'")

    if result == None:
        return

    lock.acquire()
    activeJobs = activeJobs + 1
    lock.release()

    thread = JobThread(jobId, lock)
    thread.setName("job-" + `int(jobId)`)
    thread.start()

def indexInputFiles(extension):
    result = executeSQLQuery("SELECT filename FROM " + dbInputsTable)
    if result == None:
        return

    for job in result:
        filename = job[0]
        if not os.path.isfile(filename):
            print filename + " has gone away..."
            executeSQLQuery("DELETE FROM " + dbInputsTable + \
                    " WHERE filename='" + filename + "'")

    inputDirectory = os.path.abspath(getSetting("input-directory"))
    for filename in glob.glob(inputDirectory + "/*." + extension):
        result = executeSQLQuery("SELECT filename FROM " + dbInputsTable + \
                " WHERE filename='" + filename + "'")
        if len(result) == 0:
            print "Indexing " + filename + "..."
            executeSQLQuery("INSERT INTO " + dbInputsTable + " "\
                    "(filename, type) " + \
                    "VALUES('" + filename + "', '" + extension + "')")

def updateAvailableInputFiles(lock):
    """Update the list of input files that can be used"""
    indexInputFiles("tab")
    indexInputFiles("gtf")
    indexInputFiles("bam")

def checkForNewJobs(lock):
    """Deal with any jobs that are waiting to start"""

    global activeJobs

    maxJobs = getSetting("max-jobs")

    result = executeSQLQuery("SELECT id, timequeued, timestarted, timefinished " + \
            "FROM " + dbJobsTable + " " + \
            "WHERE timestarted = '0' " + \
            "AND abort = '0' " + \
            "ORDER BY id")
    if result == None:
        return

    for job in result:
        lock.acquire()

        # Set queue time
        if job[1] == 0:
            result2 = executeSQLQuery("UPDATE " + dbJobsTable + " SET timequeued = '" + \
                `int(time.time())` + "' WHERE id = '" + `int(job[0])` + "'")
            if result2 == None:
              lock.release()
              break

        if activeJobs < int(maxJobs):
            lock.release()
            startJob(job[0], lock)
        else:
            lock.release()

def sendmail(jobId, recipient):
    # Send an email
    sender = getSetting("from-address")
    to = []
    to.append(recipient)

    url = getSetting("base-url")
    body = "Results for job " + jobId + " are now available:\n" + \
                url + "results.php?job=" + jobId + "\n"

    message = """\
From: %s
To: %s
Subject: %s

%s
""" % (sender, ", ".join(to), "seq-graph job " + jobId + " results", body)

    try:
        sendmailProcess = os.popen("sendmail -t -i", "w")
        sendmailProcess.write(message)
        status = sendmailProcess.close()
        if status:
            print "WARNING: sendmail exit status", status

    except:
        print "WARNING: Failed to deliver"

def checkForCompleteJobs(lock):
    """Deal with any jobs that have just completed"""

    # Set the finish time for any aborted jobs
    result = executeSQLQuery("UPDATE " + dbJobsTable + \
            " SET timefinished = '" + \
            `int(time.time())` + "' " + \
            "WHERE timefinished = '0' " + \
            "AND abort = '1'")
    if result == None:
        return

    result = executeSQLQuery("SELECT id, email, timefinished FROM " + dbJobsTable + \
            " WHERE notified = '0'")
    for job in result:
        if job[2] != 0:
            print "Job " + `int(job[0])` + " completed, notifying '" + job[1] + "'"

            # Send an email
            sendmail(`int(job[0])`, job[1])

            executeSQLQuery("UPDATE " + dbJobsTable + " SET notified = '1'" + \
                    " WHERE id = '" + `int(job[0])` + "'")

def purgeHistoricalJobs(lock):
    """Remove old jobs in order to save disk space"""

    now = time.time()
    cutoff = now - (60 * 60 * 24 * 14)

    result = executeSQLQuery("SELECT id, resultsdir FROM " + dbJobsTable + \
            " WHERE timefinished > 0 AND timefinished < '" + `int(cutoff)` + "'")
    for job in result:
        jobId = job[0]
        resultsDir = job[1]
        print "Job " + `int(jobId)` + " is old, purging"
        executeSQLQuery("DELETE FROM " + dbResultsTable + " WHERE id='" + `int(jobId)` + "'")
        executeSQLQuery("DELETE FROM " + dbJobsTable + " WHERE id='" + `int(jobId)` + "'")
        if os.path.exists(resultsDir):
            shutil.rmtree(resultsDir)

def sigHandler(signal, stackFrame):
    """Signal handler"""

    global exitNow
    exitNow = exitNow + 1

    # Abort any jobs that aren't yet finished
    print "Caught signal, aborting jobs..."
    executeSQLQuery("UPDATE " + dbJobsTable + \
            " SET abort = '1'" + \
            " AND timefinished = 0")
    print "done."

def initialiseDb(formatDb, sqlFilename):
    db = MySQLdb.connect(host = dbHost, user = dbUser, passwd = dbPass, db = dbName)
    if db == None:
      return False

    cursor = db.cursor()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        if formatDb:
            print "Dropping all tables..."
            cursor.execute("DROP TABLE IF EXISTS " + dbSettingsTable)
            cursor.execute("DROP TABLE IF EXISTS " + dbJobsTable)
            cursor.execute("DROP TABLE IF EXISTS " + dbResultsTable)
            cursor.execute("DROP TABLE IF EXISTS " + dbInputsTable)

        cursor.execute("CREATE TABLE IF NOT EXISTS " + dbSettingsTable + " (" + \
            "setting VARCHAR(255) PRIMARY KEY NOT NULL, " + \
            "value TEXT NOT NULL" + \
            ")")

        cursor.execute("CREATE TABLE IF NOT EXISTS " + dbJobsTable + " (" + \
            "id INTEGER PRIMARY KEY AUTO_INCREMENT, " + \
            "timequeued INT NOT NULL, " + \
            "timestarted INT NOT NULL, " + \
            "timefinished INT NOT NULL, " + \
            "exitcode INT NOT NULL, " + \
            "arguments TEXT NOT NULL, " + \
            "resultsdir TEXT NOT NULL, " + \
            "abort INT NOT NULL, " + \
            "notified INT NOT NULL, " + \
            "email TEXT NOT NULL, " + \
            "output TEXT NOT NULL" + \
            ")")

        cursor.execute("CREATE TABLE IF NOT EXISTS " + dbResultsTable + " (" + \
            "id INTEGER PRIMARY KEY AUTO_INCREMENT, " + \
            "jobid INT NOT NULL, " + \
            "filename TEXT NOT NULL" + \
            ")")

        cursor.execute("CREATE TABLE IF NOT EXISTS " + dbInputsTable + " (" + \
            "filename VARCHAR(255) NOT NULL PRIMARY KEY, " + \
            "type TEXT NOT NULL" + \
            ")")

        cursor.execute("DELETE FROM " + dbInputsTable)
        db.commit()

    if sqlFilename != None:
        try:
            with open(sqlFilename, "rb") as sqlFile:
                print("Executing " + sqlFilename + "...")
                sql = sqlFile.read()
                cursor.execute(sql)
                db.commit()
        except IOError:
            print("Failed to open " + sqlFilename)
            return False
        except:
            print("Failed to execute SQL")
            print sys.exc_info()[0]
            return False
        finally:
            db.close()

    db.close()
    return True

def main():
    """Main program"""

    print "Sequence graph generation web frontend daemon\n(c) The Roslin Institute 2013-2014\n"

    parser = OptionParser()
    parser.add_option("-f", "--format", action="store_true", dest="formatDb", default=False, help="format the database")
    parser.add_option("-s", "--sql", dest="sqlFilename", help="a file containing SQL to execute", metavar="FILE")
    (options, args) = parser.parse_args()

    signal.signal(signal.SIGINT, sigHandler)
    signal.signal(signal.SIGTERM, sigHandler)

    if not loadDbSettings():
        print("Failed to load database settings")
        return

    if initialiseDb(options.formatDb, options.sqlFilename):
        lock = threading.Lock()

        while exitNow == 0:
            updateAvailableInputFiles(lock)
            checkForNewJobs(lock)
            checkForCompleteJobs(lock)
            purgeHistoricalJobs(lock)

            # Wait a bit
            time.sleep(3)

        # Take a local copy of the currently active threads
        lock.acquire()
        global activeThreads
        threadList = activeThreads[:]
        lock.release()

        # .join() each potentially active thread
        for thread in threadList:
            thread.join()

        checkForCompleteJobs(lock)

if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        sys.exit(sys.exc_info()[1])
    except:
        print "Unhandled exception:", sys.exc_info()[0]
        traceback.print_exc()
