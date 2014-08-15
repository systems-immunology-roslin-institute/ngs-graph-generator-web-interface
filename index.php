<?php
    include( "shared.php" );

    // Store email cookie for a year
    $email = $_POST[ 'email' ];
    if( $email != NULL )
        setcookie( "seqgraph_email", "$email", time() + 60 * 60 * 24 * 365 );
?>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
    <title>NGS graph generator</title>
    <link rel="stylesheet" type="text/css" href="style.css">
</head>
<script language="JavaScript">
    function queueFormSubmit( action )
    {
        document.queue.action = action;
        document.queue.submit( );

        return true;
    }
</script>

<body>
    <div class="headerfooter">
        <div class="header">NGS graph generator</div>
        <a href=".">Scheduler</a>
        <a href="results.php">Results</a>
    </div>
<?php
    // This lock may not be strictly necessary, but
    // it's not doing any harm
    $lockFileName = "/tmp/seqgraph.php.lock";
    $lockFile = 0;

    /**
     * Take the lock
     */
    function takeLock( )
    {
        global $lockFileName;
        global $lockFile;

        $lockFile = fopen( $lockFileName, "w" );
        flock( $lockFile, LOCK_EX );
    }

    /**
     * Release the lock
     */
    function releaseLock( )
    {
        global $lockFileName;
        global $lockFile;

        if( $lockFile != 0 )
        {
            flock( $lockFile, LOCK_UN );
            fclose( $lockFile );
        }
    }

    if( $db = openDatabase( ) )
    {
        if( $_GET[ 'action' ] == 'submit' )
        {
?>
    <div id="queued">
        <p>
            <form>
                <fieldset>
<?php
            takeLock( );

            $bam_file = $_POST[ 'bam_file' ];
            $tab_file = $_POST[ 'tab_file' ];
            $gtf_file = $_POST[ 'gtf_file' ];
            $similarity = $_POST[ 'similarity' ];
            $coverage = $_POST[ 'coverage' ];
            $identical_unique = $_POST[ 'identical_unique' ];
            $genes = $_POST[ 'genes' ];
            $email = $_POST[ 'email' ];
            $geneCheck = '^[a-zA-Z0-9, \t\n]+$';
            if( strlen( $genes ) != 0 && eregi( $geneCheck, $genes ) )
            {
                // Check an email address has been given
                if( strlen( $email ) != 0 )
                {
                    // Check email address is valid
                    $emailCheck = '^[a-z0-9_\+-]+(\.[a-z0-9_\+-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*\.([a-z]{2,4})$';
                    if( eregi( $emailCheck, $email ) )
                    {
                        // Has the email address been checked that it is real
                        $query = $db->prepare( "SELECT DISTINCT validated FROM jobs WHERE email = ? AND validated = '1'" );
                        $query->bind_param( "s", $email );

                        $query->execute( )
                            or die( "Query failed: " . $db->error );

                        $result = $query->get_result( );
                        $validated = ( $result->num_rows > 0 );

                        $result = $db->query( "SHOW TABLE STATUS LIKE 'jobs'" )
                            or die( "Query failed: " . $db->error );
                        $row = $result->fetch_array( );
                        $nextJobId = $row['Auto_increment'];
                        $outputDirectory = getSetting("output-directory");
                        if( $outputDirectory == "" )
                            $outputDirectory = ".";
                        $cacheDirectory = $outputDirectory;
                        $outputDirectory .= "/job-$nextJobId";

                        $arguments = 
                            "-b $bam_file -t $tab_file -g $gtf_file -o $outputDirectory " .
                            "-c $cacheDirectory " . ($identical_unique ? "-u " : "") .
                            "-d \"$genes\" -p $similarity -l $coverage";

                        // Add new job
                        $query = $db->prepare( "INSERT INTO jobs ( email, arguments, resultsdir ) VALUES ( ?, ?, ? )" );
                        $query->bind_param( "sss", $email, $arguments, $outputDirectory );

                        $query->execute( )
                            or die( "Query failed: " . $db->error );

                        $jobId = $db->insert_id;

                        if( $validated )
                            echo "<p>Queuing <a href=\"results.php?job=$jobId\">job $jobId</a></p>\n";
                        else
                            echo "<p>Your email address requires validation, " .
                                "please click on the link that has been sent to you</p>\n";

                        echo "<a href=\".\">Back</a>\n";
                    }
                    else
                    {
                        echo "<p>\"$email\" is not a valid email address</p>\n";
                        echo "<a href=\".\">Back</a>\n";
                    }
                }
                else
                {
                    echo "<p>No email address supplied</p>\n";
                    echo "<a href=\".\">Back</a>\n";
                }
            }
            else
            {
                echo "<p>No gene list supplied or malformed</p>\n";
                echo "<a href=\".\">Back</a>\n";
            }

            releaseLock( );
?>
                </fieldset>
            </form>
        </p>
    </div>
<?php
        }
        else if( $_GET[ 'action' ] == 'validate' )
        {
?>
    <div id="queued">
        <p>
            <fieldset>
<?php
            takeLock( );

            $token = $_GET[ 'token' ];

            $query = $db->prepare( "SELECT id, email FROM jobs WHERE token = ? AND validated = '0'" );
            $query->bind_param( "s", $token );

            $query->execute( )
                or die( "Query failed: " . $db->error );
            $result = $query->get_result( );

            if( $result->num_rows > 0 )
            {
                echo "<p>Your queued jobs will now be executed:</p><p>\n";
                while( $row = $result->fetch_assoc( ) )
                {
                    $jobId = $row[ 'id' ];
                    $email = $row[ 'email' ];
                    echo "<a href=\"results.php?job=$jobId\">Job $jobId</a>\n";
                }

                echo "</p>\n";

                $query = $db->prepare( "UPDATE jobs SET validated = '1' WHERE email = ?" );
                $query->bind_param( "s", $email );

                $query->execute( )
                    or die( "Query failed: " . $db->error );
            }
            else
            {
                echo "<p>This validation token has expired, please try again</p>\n";
            }

            releaseLock( );
?>
            </fieldset>
        </p>
    </div>
<?php
        }
        else
        {
?>
    <form name="queue" enctype="multipart/form-data" method="post" action="?action=submit">
        <div id="settings">
            <p>
                <fieldset class="outer">
                    <legend>
                        Settings
                    </legend>

                    <p>
                        <label>BAM file</label>
                        <select name="bam_file">
<?php
            $inputsResult = $db->query( "SELECT filename FROM inputs WHERE type = 'bam'" )
                or die( "Query failed: " . $db->error );

            while( $row = $inputsResult->fetch_assoc( ) )
            {
                $filename = $row[ 'filename' ];
                $absFilename = basename($filename);
                echo "<option value=\"$filename\">$absFilename</option>";
            }
?>
                        </select>
                    </p>
                    <p>
                        <label>Chromosome length file</label>
                        <select name="tab_file">
<?php
            $inputsResult = $db->query( "SELECT filename FROM inputs WHERE type = 'tab'" )
                or die( "Query failed: " . $db->error );

            while( $row = $inputsResult->fetch_assoc( ) )
            {
                $filename = $row[ 'filename' ];
                $absFilename = basename($filename);
                echo "<option value=\"$filename\">$absFilename</option>";
            }
            mysql_free_result( $inputsResult );
?>
                        </select>
                    </p>
                    <p>
                        <label>GTF file</label>
                        <select name="gtf_file">
<?php
            $inputsResult = $db->query( "SELECT filename FROM inputs WHERE type = 'gtf'" )
                or die( "Query failed: " . $db->error );

            while( $row = $inputsResult->fetch_assoc( ) )
            {
                $filename = $row[ 'filename' ];
                $absFilename = basename($filename);
                echo "<option value=\"$filename\">$absFilename</option>";
            }
            mysql_free_result( $inputsResult );
?>
                        </select>
                    </p>
                    <p>
                        <label>Percentage sequence similarity</label>
                        <input class="num" type="text" name="similarity" value="98" /> %
                    </p>
                    <p>
                        <label>Percentage sequence coverage</label>
                        <input class="num" type="text" name="coverage" value="31" /> %
                    </p>
                    <p>
                        <label>Discard identical reads</label>
                        <input type="checkbox" name="identical_unique" value="1" checked/>
                    </p>
                    <p>
                        <label>Gene names</label> <input type="text" name="genes" id="genes" />
                    </p>
                    <p>
                        <label>Email</label> <input type="text" name="email" id="email" />
                    </p>
                    <p id="control_buttons">
                        <a class="button" id="queueLink" href="#queueLink"
                            onclick="JavaScript: return queueFormSubmit( '?action=submit' );">Schedule job</a>
                    </p>
                </fieldset>
            </p>
        </div>
    </form>
<?php
        }
?>
    <div class="headerfooter footer"></div>
<?php

        closeDatabase( $db );
    }
?>
</body>
</html>
