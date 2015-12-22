#! /usr/bin/python
#
# Daemon for seq graph web frontend
#
# Copyright (C) The University of Edinburgh, 2013-2014. All Rights Reserved.

from email.mime.text import MIMEText
from optparse import OptionParser
import glob
import json
import MySQLdb
import os
import shlex
import shutil
import signal
import string
import subprocess
import sys
import threading
import time
import traceback
import urllib
import urlparse
import warnings

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
activeJobs      = 0
activeThreads   = []

maxJobSize = 10737418240 # 10Gb

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

def getPathSize(path):
    total = 0
    for dirPath, dirNames, fileNames in os.walk(path):
        for fileName in fileNames:
            fqFileName = os.path.join(dirPath, fileName)
            if os.path.exists(fqFileName):
                total += os.lstat(fqFileName).st_size

    return total

def updateJobSize(jobId):
    result = executeSQLQuery("SELECT id, resultsDir " + \
            "FROM " + dbJobsTable + " " + \
            "WHERE id = " + `int(jobId)`)
    if result == None:
        return

    for job in result:
        jobId = job[0]
        resultsDir = os.path.abspath(job[1])
        pathSize = getPathSize(resultsDir)
        executeSQLQuery("UPDATE " + dbJobsTable + " SET size = '" + \
            `pathSize` + "' WHERE id = '" + `int(jobId)` + "'")

def updateJobSizes():
    print "Updating job sizes"
    result = executeSQLQuery("SELECT id " + \
            "FROM " + dbJobsTable + " " + \
            "WHERE validated = '1' " + \
            "ORDER BY id")
    if result == None:
        return

    for job in result:
        updateJobSize(job[0])

class ConsoleReadingThread(threading.Thread):
    def __init__(self, out, jobId):
        """Constructor for job thread"""

        threading.Thread.__init__(self)
        self.out = out
        self.jobId  = jobId

    def run(self):
        """Main thread functionality"""

        try:
            allOutput = ""
            for line in iter(self.out.readline, ''):
                allOutput = allOutput + line
                executeSQLQuery("UPDATE " + dbJobsTable + " SET output = '" + \
                    MySQLdb.escape_string(allOutput) + \
                    "' WHERE id = '" + `int(self.jobId)` + "'")
            self.out.close()
            print "Output exhausted for job " + `int(self.jobId)`

        except:
            print "Warning, unhandled exception in console reading thread"
            traceback.print_exc()

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
            consoleReadingThread = None
            script = getSetting("script-file")

            result = executeSQLQuery("SELECT id, arguments, resultsDir FROM " + \
                    dbJobsTable + " WHERE id = '" + `int(self.jobId)` + "'")

            if len(result) == 1:
                row = result[0]
                jobId = row[0]
                arguments = row[1]
                resultsDir = os.path.abspath(row[2])

                scriptWithOptionsText = script + " " + arguments
                scriptWithOptionsArray = shlex.split(scriptWithOptionsText)

                # Start script
                scriptProcess = subprocess.Popen(scriptWithOptionsArray, shell=False, \
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, \
                    close_fds=True, preexec_fn=os.setsid)

                consoleReadingThread = ConsoleReadingThread(scriptProcess.stdout, jobId)
                consoleReadingThread.setName("job-" + `int(jobId)` + "-reader")
                consoleReadingThread.start()

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

                            # This is a bit rude, but reliable
                            os.killpg(scriptProcess.pid, signal.SIGKILL)
                            break
                            
                    time.sleep(3)

                    exitCode = scriptProcess.poll()

                    # If still running, suspend
                    if exitCode == None:
                        os.kill(scriptProcess.pid, signal.SIGSTOP)

                    updateJobSize(jobId)

                    # Resume
                    if exitCode == None:
                        os.kill(scriptProcess.pid, signal.SIGCONT)

                # Wait for script to complete
                consoleReadingThread.join()
                consoleReadingThread = None
                scriptProcess.wait()

                print "Finished job " + `int(jobId)`

                # Set finished time stamp
                executeSQLQuery("UPDATE " + dbJobsTable + " SET timefinished = '" + \
                    `int(time.time())` + "', exitcode = '" + `int(exitCode)` + \
                    "' WHERE id = '" + `int(jobId)` + "'")

                if not self.abort and os.path.exists(resultsDir):
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
        finally:
            if consoleReadingThread != None:
                consoleReadingThread.join()

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

def sendmail(recipient, subject, body):
    # Send an email
    sender = getSetting("from-address")

    message = MIMEText(body)
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject

    try:
        sendmailProcess = subprocess.Popen(["sendmail", "-t"], \
            stdin=subprocess.PIPE, close_fds=True)
        sendmailProcess.communicate(message.as_string())
        if sendmailProcess.returncode != 0:
            print "WARNING: sendmail exit status", sendmailProcess.returncode

        print "Emailed " + recipient + " \"" + subject + "\""

    except:
        print "WARNING: Failed to deliver"

def purgeJob(jobId):
    """Remove old job to save disk space"""

    print "Purging job " + `int(jobId)`
    result = executeSQLQuery("SELECT resultsdir FROM " + dbJobsTable + \
            " WHERE id = '" + `int(jobId)` + "'")
    if len(result) == 0:
        return

    resultsDir = result[0][0]

    executeSQLQuery("DELETE FROM " + dbResultsTable + " WHERE id='" + `int(jobId)` + "'")
    executeSQLQuery("DELETE FROM " + dbJobsTable + " WHERE id='" + `int(jobId)` + "'")
    if os.path.exists(resultsDir):
        shutil.rmtree(resultsDir)

def abortJob(jobId):
    """Signal job thread to abort a job"""

    print "Aborting job " + `int(jobId)`
    result = executeSQLQuery("UPDATE " + dbJobsTable + \
            " SET abort = 1" + \
            " AND timefinished = 0" + \
            " WHERE id = '" + `int(jobId)` + "'")

def cleanResultsDirOfAbortedJobs(lock):
    result = executeSQLQuery("SELECT id, resultsdir " + \
            "FROM " + dbJobsTable + " " + \
            "WHERE timefinished > 0 " + \
            "AND abort = 1")
    if result == None:
        return

    for job in result:
        jobId = job[0]
        resultsDir = os.path.abspath(job[1])

        abortedIndicator = os.path.join(resultsDir, "aborted")
        if not os.path.exists(abortedIndicator):
            print "Cleaning aborted results from job " + `int(jobId)`

            for root, dirs, files in os.walk(resultsDir, topdown=False):
                for file in files:
                    filepath = os.path.join(root, file)
                    os.remove(filepath)
                for dir in dirs:
                    dirpath = os.path.join(root, dir)
                    if os.path.islink(dirpath):
                        os.unlink(dirpath)
                    else:
                        os.rmdir(dirpath)

            # Indicate job was aborted
            open(abortedIndicator, 'a').close()
            updateJobSize(jobId)

def checkForExcessivelyLargeJobs(lock):
    result = executeSQLQuery("SELECT id, size " + \
            "FROM " + dbJobsTable + " " + \
            "WHERE timefinished = 0 " + \
            "AND size >= " + `int(maxJobSize)` + " " \
            "AND abort = 0")
    if result == None:
        return

    for job in result:
        jobId = job[0]
        print "Job " + `int(jobId)` + " is too large"
        abortJob(jobId)

def purgeJobsWhereResultsDirIsMissing(lock):
    result = executeSQLQuery("SELECT id, resultsdir " + \
            "FROM " + dbJobsTable + " " + \
            "WHERE timefinished > 0 OR abort = 1")
    if result == None:
        return

    for job in result:
        jobId = job[0]
        resultsDir = os.path.abspath(job[1])
        if not os.path.exists(resultsDir):
            print "Job " + `int(jobId)` + " is missing results directory"
            purgeJob(jobId)

def checkForUnvalidatedEmailAddresses(lock):
    """Check if there are any jobs whose email addresses have not yet been checked"""

    # Avoid revalidating email addresses
    result = executeSQLQuery("SELECT DISTINCT email, token " + \
            "FROM " + dbJobsTable + " " + \
            "WHERE validated = '1' " + \
            "ORDER BY id")
    for job in result:
        email = job[0]
        token = job[1]
        executeSQLQuery("UPDATE " + dbJobsTable + \
            " SET validated = '1'," + \
            " token = '" + token + "'" + \
            " WHERE email = '" + email + "'")

    result = executeSQLQuery("SELECT id, email, token, timequeued " + \
            "FROM " + dbJobsTable + " " + \
            "WHERE validated = '0' " + \
            "ORDER BY id")
    if result == None:
        return

    for job in result:
        jobId = job[0]
        email = job[1]
        token = job[2]
        timequeued = int(job[3])

        if len(token) == 0:
            # Generate token
            newToken = os.urandom(16).encode('hex')

            print "Validating " + email + " with token " + newToken

            # Send email
            subject = "NGS Graph Generator needs to validate your email address"
            url = getSetting("base-url")
            body = "Dear User,\n\n" + "Thank you for using our NGS Grapah Generator to analyse and visualise your RNA-seq data. To ensure that you can use our pipeline, you need to click the following link to start building your graph.\n\n" + url + "generate.php?action=validate" + "&token=" + newToken 
	    
            sendmail(email, subject, body)

            # Update table with token
            executeSQLQuery("UPDATE " + dbJobsTable + \
                    " SET token = '" + \
                    newToken + "' " + \
                    "WHERE email = '" + email + "'")
        else:
            now = time.time()
            cutoff = now - (60 * 60 * 2) # 2 hours
            if timequeued < cutoff:
                print "Email " + email + " validation timed out"
                purgeJob(jobId)


def checkForNewJobs(lock):
    """Deal with any jobs that are waiting to start"""

    global activeJobs

    maxJobs = getSetting("max-jobs")

    result = executeSQLQuery("SELECT id, timequeued, validated, email, token " + \
            "FROM " + dbJobsTable + " " + \
            "WHERE timestarted = '0' " + \
            "AND abort = '0' " + \
            "ORDER BY id")
    if result == None:
        return

    for job in result:
        lock.acquire()

        jobId = `int(job[0])`
        timeQueued = job[1]
        validated = job[2]
        email = job[3]
        token = job[4]

        # Set queue time
        if timeQueued == 0:
            result2 = executeSQLQuery("UPDATE " + dbJobsTable + " SET timequeued = '" + \
                `int(time.time())` + "' WHERE id = '" + jobId + "'")
            if result2 == None:
                lock.release()
                break

        if validated != 0 and activeJobs < int(maxJobs):
            lock.release()
            startJob(job[0], lock)

            # Send email
            # subject = "NGS Graph Generator job " + jobId + " started"
            # url = getSetting("base-url")
            # body = "If you happened to run a wrong job and want to abort the recent run please click the following URL to abort the job:\n" + \
            #    url + "abort.php?job=" + jobId + \
            #    "&token=" + token
		
		# Send email
            subject = "NGS Graph Generator job " + jobId + " started"
            url = getSetting("base-url")
            body = "View all your results:\n" + \
                url + "results.php?job=" + jobId + \
                "&token=" + token
		


	
            sendmail(email, subject, body)
        else:
            lock.release()

def checkForCompleteJobs(lock):
    """Deal with any jobs that have just completed"""

    result = executeSQLQuery("SELECT id, email, timefinished, abort, size, token FROM " + dbJobsTable + \
            " WHERE notified = '0'")
    for job in result:
        jobId = `int(job[0])`
        email = job[1]
        abort = int(job[3])
        size = int(job[4])
        token = job[5]
        if job[2] != 0:
            # Send an email
            url = getSetting("base-url")

            if abort == 0:
                subject = "NGS Graph Generator - seq-graph job " + jobId + " results"
                body = "Results for job " + jobId + " are now available:\n" + \
                    url + "results.php?job=" + jobId + "&token=" + token + "\n"
            else:
                subject = "NGS Graph Generator - seq-graph job " + jobId + " aborted"
                if size > maxJobSize:
                    body = "Job " + jobId +  " was automatically aborted " + \
                        "because it was using too much storage.\n"
                else:
                    body = "Job " + jobId +  " was aborted.\n"

            body = body + "\nAll of your results:\n" + \
                url + "results.php?token=" + token + "\n"

            sendmail(email, subject, body)

            executeSQLQuery("UPDATE " + dbJobsTable + " SET notified = '1'" + \
                    " WHERE id = '" + jobId + "'")

def purgeHistoricalJobs(lock):
    """Remove old jobs in order to save disk space"""

    now = time.time()
    cutoff = now - (60 * 60 * 24 * 7) # 1 week

    result = executeSQLQuery("SELECT id, resultsdir FROM " + dbJobsTable + \
            " WHERE timefinished > 0 AND timefinished < '" + `int(cutoff)` + "'")
    for job in result:
        jobId = job[0]
        resultsDir = job[1]
        print "Job " + `int(jobId)` + " is old"
        purgeJob(jobId)

def sigHandler(signal, stackFrame):
    """Signal handler"""

    global exitNow
    exitNow = exitNow + 1

    # Abort any jobs that aren't yet finished
    print "Caught signal, aborting jobs..."
    executeSQLQuery("UPDATE " + dbJobsTable + \
            " SET abort = 1" + \
            " WHERE timefinished = 0")
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
            "description TEXT NOT NULL, " + \
            "resultsdir TEXT NOT NULL, " + \
            "abort INT NOT NULL, " + \
            "notified INT NOT NULL, " + \
            "email TEXT NOT NULL, " + \
            "validated TINYINT NOT NULL, " + \
            "token TEXT NOT NULL, " + \
            "output MEDIUMTEXT NOT NULL, " + \
            "size BIGINT NOT NULL DEFAULT -1" + \
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

        updateJobSizes()

        while exitNow == 0:
            updateAvailableInputFiles(lock)
            checkForNewJobs(lock)
            checkForUnvalidatedEmailAddresses(lock)
            checkForCompleteJobs(lock)
            purgeHistoricalJobs(lock)
            purgeJobsWhereResultsDirIsMissing(lock)
            cleanResultsDirOfAbortedJobs(lock)
            checkForExcessivelyLargeJobs(lock)

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
