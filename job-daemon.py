#!/opt/apps/python/2.7.3/bin/python
#
# Daemon for seq graph web frontend
#
# Copyright (C) The University of Edinburgh, 2013. All Rights Reserved.

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

def getSetting(db, key):
    """Retrieve a setting from the database"""

    query = "SELECT value FROM " + dbSettingsTable + " WHERE setting = '" + key + "'"
    cursor = db.cursor()
    cursor.execute(query)
    result = cursor.fetchone()

    if result != None:
        return result[0]
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
            db = MySQLdb.connect(host = dbHost, user = dbUser, passwd = dbPass, db = dbName)

            script = getSetting(db, "script-file")

            cursor = db.cursor()

            query = "SELECT id, arguments, resultsDir FROM " + \
                    dbJobsTable + " WHERE id = '" + `int(self.jobId)` + "'"
            cursor.execute(query)
            result = cursor.fetchone()
            db.commit()

            if result != None:
                jobId = result[0]
                arguments = result[1]
                resultsDir = result[2]

                scriptWithOptions = script + " " + arguments

                # Start script
                scriptProcess = subprocess.Popen(scriptWithOptions, shell=True)
                exitCode = scriptProcess.poll()

                while exitCode == None:
                    # Check for abort requests
                    if self.abort == False:
                        query = "SELECT abort FROM " + dbJobsTable + \
                                " WHERE id = '" + `int(self.jobId)` + "'"
                        cursor = db.cursor()
                        cursor.execute(query)
                        result = cursor.fetchone()
                        db.commit()

                        if result == None or result[0] != 0:
                            print "Aborting job " + `int(self.jobId)`
                            self.abort = True
                            scriptProcess.terminate()
                            break
                            
                    time.sleep(3)
                    exitCode = scriptProcess.poll()

                # Wait for script to complete
                scriptProcess.wait()

                # Set finished time stamp
                query = "UPDATE " + dbJobsTable + " SET timefinished = '" + \
                    `int(time.time())` + "', exitcode = '" + `int(exitCode)` + \
                    "' WHERE id = '" + `int(self.jobId)` + "'"

                cursor = db.cursor()
                cursor.execute(query)
                db.commit()

                print "Finished job " + `int(self.jobId)`

                resultsDir = os.path.abspath(resultsDir)
                if os.path.exists(resultsDir):
                    print "Finding results in " + resultsDir
                    layoutFilenames = glob.glob(resultsDir + "/*.layout")

                    for layoutFilename in layoutFilenames:
                        print "...storing " + layoutFilename
                        with open(layoutFilename, "rb") as layoutFile:
                            blob = layoutFile.read()
                            data = MySQLdb.Binary(blob)
                            layoutFilebasename = os.path.basename(layoutFilename)
                            cursor = db.cursor()
                            cursor.execute("INSERT INTO " + dbResultsTable + " (jobid, filename, data) " + \
                                    "VALUES('" + `int(self.jobId)` + "', '" + layoutFilebasename + "', %s)", \
                                    (data,))
                            db.commit()

            self.lock.acquire()
            activeThreads.remove(self)
            activeJobs = activeJobs - 1
            self.lock.release()
        except:
            print "Warning, unhandled exception in job thread"
            traceback.print_exc()

        db.close()

def startJob(db, jobId, lock):
    """Start a job"""

    global activeJobs

    print "Starting job " + `int(jobId)`

    query = "UPDATE " + dbJobsTable + " SET timestarted = '" + \
        `int(time.time())` + "' WHERE id = '" + `int(jobId)` + "'"
    cursor = db.cursor()
    cursor.execute(query)
    db.commit()

    lock.acquire()
    activeJobs = activeJobs + 1
    lock.release()

    thread = JobThread(jobId, lock)
    thread.setName("job-" + `int(jobId)`)
    thread.start()
    return

def indexInputFiles(db, extension):
    cursor = db.cursor()
    cursor.execute("SELECT filename FROM " + dbInputsTable)
    result = cursor.fetchall()
    db.commit()

    for job in result:
        filename = job[0]
        if not os.path.isfile(filename):
            print filename + " has gone away..."
            cursor.execute("DELETE FROM " + dbInputsTable + \
                    " WHERE filename='" + filename + "'")
            db.commit()

    inputDirectory = os.path.abspath(getSetting(db, "input-directory"))
    cursor = db.cursor()
    for filename in glob.glob(inputDirectory + "/*." + extension):
        cursor.execute("SELECT filename FROM " + dbInputsTable + \
                " WHERE filename='" + filename + "'")
        db.commit()
        if cursor.fetchone() == None:
            print "Indexing " + filename + "..."
            cursor.execute("INSERT INTO " + dbInputsTable + " "\
                    "(filename, type) " + \
                    "VALUES('" + filename + "', '" + extension + "')")
            db.commit()

def updateAvailableInputFiles(db, lock):
    """Update the list of input files that can be used"""
    indexInputFiles(db, "tab")
    indexInputFiles(db, "gtf")
    indexInputFiles(db, "bam")

def checkForNewJobs(db, lock):
    """Deal with any jobs that are waiting to start"""

    global activeJobs

    maxJobs = getSetting(db, "max-jobs")

    query = "SELECT id, timequeued, timestarted, timefinished " + \
            "FROM " + dbJobsTable + " " + \
            "WHERE timestarted = '0' " + \
            "AND abort = '0' " + \
            "ORDER BY id"
    cursor = db.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    db.commit()

    for job in result:
        lock.acquire()

        # Set queue time
        if job[1] == 0:
            query = "UPDATE " + dbJobsTable + " SET timequeued = '" + \
                `int(time.time())` + "' WHERE id = '" + `int(job[0])` + "'"
            cursor = db.cursor()
            cursor.execute(query)
            db.commit()

        if activeJobs < int(maxJobs):
            lock.release()
            startJob(db, job[0], lock)
        else:
            lock.release()

def sendmail(db, jobId, recipient):
    # Send an email
    sender = getSetting(db, "from-address")
    to = []
    to.append(recipient)

    url = getSetting(db, "base-url")
    body = "Results for job " + jobId + " are now available:\n" + \
                url + "results.php?job=" + jobId + "\n"

    message = """\
From: %s
To: %s
Subject: %s

%s
""" % (sender, ", ".join(to), "Job " + jobId + " results", body)

    try:
        sendmailProcess = os.popen("sendmail -t -i", "w")
        sendmailProcess.write(message)
        status = sendmailProcess.close()
        if status:
            print "WARNING: sendmail exit status", status

    except:
        print "WARNING: Failed to deliver"

def checkForCompleteJobs(db, lock):
    """Deal with any jobs that have just completed"""

    cursor = db.cursor()

    # Set the finish time for any aborted jobs
    query = "UPDATE " + dbJobsTable + \
            " SET timefinished = '" + \
            `int(time.time())` + "' " + \
            "WHERE timefinished = '0' " + \
            "AND abort = '1'"
    cursor.execute(query)
    db.commit()

    query = "SELECT id, email, timefinished FROM " + dbJobsTable + \
            " WHERE notified = '0'"
    cursor.execute(query)
    result = cursor.fetchall()
    for job in result:
        if job[2] != 0:
            print "Job " + `int(job[0])` + " completed, notifying '" + job[1] + "'"

            # Send an email
            sendmail(db, `int(job[0])`, job[1])

            query = "UPDATE " + dbJobsTable + " SET notified = '1'" + \
                    " WHERE id = '" + `int(job[0])` + "'"
            cursor.execute(query)
            db.commit()

def sigHandler(signal, stackFrame):
    """Signal handler"""

    global exitNow
    exitNow = exitNow + 1

    db = MySQLdb.connect(host = dbHost, user = dbUser, passwd = dbPass, db = dbName)

    if db != None:
        # Abort any jobs that aren't yet finished
        print "Caught signal, aborting jobs..."
        query = "UPDATE " + dbJobsTable + \
                " SET abort = '1'" + \
                " AND timefinished = 0"
        cursor = db.cursor()
        cursor.execute(query)
        db.commit()
        print "done."

        db.close()

def initialiseDb(db, formatDb, sqlFilename):
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
            "email TEXT NOT NULL" + \
            ")")

        cursor.execute("CREATE TABLE IF NOT EXISTS " + dbResultsTable + " (" + \
            "id INTEGER PRIMARY KEY AUTO_INCREMENT, " + \
            "jobid INT NOT NULL, " + \
            "filename TEXT NOT NULL, " + \
            "data LONGBLOB NOT NULL" + \
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

    return True

def main():
    """Main program"""

    print "Sequence graph generation web frontend daemon\n(c) The Roslin Institute 2013\n"

    parser = OptionParser()
    parser.add_option("-f", "--format", action="store_true", dest="formatDb", default=False, help="format the database")
    parser.add_option("-s", "--sql", dest="sqlFilename", help="a file containing SQL to execute", metavar="FILE")
    (options, args) = parser.parse_args()

    signal.signal(signal.SIGINT, sigHandler)
    signal.signal(signal.SIGTERM, sigHandler)

    if not loadDbSettings():
        print("Failed to load database settings")
        return

    db = MySQLdb.connect(host = dbHost, user = dbUser, passwd = dbPass, db = dbName)
    if db != None and initialiseDb(db, options.formatDb, options.sqlFilename):
        lock = threading.Lock()

        while exitNow == 0:
            updateAvailableInputFiles(db, lock)
            checkForNewJobs(db, lock)
            checkForCompleteJobs(db, lock)

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

        checkForCompleteJobs(db, lock)
        db.close()

if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        sys.exit(sys.exc_info()[1])
    except:
        print "Unhandled exception:", sys.exc_info()[0]
        traceback.print_exc()
