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
            takeLock( );

            $bam_file = $_POST[ 'bam_file' ];
            $tab_file = $_POST[ 'tab_file' ];
            $gtf_file = $_POST[ 'gtf_file' ];
            $similarity = $_POST[ 'similarity' ];
            $coverage = $_POST[ 'coverage' ];
            $genes = $_POST[ 'genes' ];
            $email = $_POST[ 'email' ];
?>
    <div id="queued">
        <p>
            <form>
                <fieldset>
<?php
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
                        $row = mysql_fetch_array( mysql_query( "SHOW TABLE STATUS LIKE '$dbJobsTable'" ) );
                        $nextJobId = $row['Auto_increment'];
                        $outputDirectory = "./job-$nextJobId";

                        // Add new job
                        $query = "INSERT INTO $dbJobsTable ( email, arguments, resultsdir ) " .
                            "VALUES ( " .
                            "'$email', " .
                            "'-b $bam_file -t $tab_file -g $gtf_file -o $outputDirectory -d \"$genes\" -p $similarity -l $coverage', " .
                            "'$outputDirectory'" .
                            ")";
                        $result = mysql_query( $query ) or
                            die( "Query '$query' failed: " . mysql_error( ) );

                        $jobId = mysql_insert_id( );

                        echo "<p>Queuing <a href=\"results.php?job=$jobId\">job $jobId</a></p>\n";
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
?>
                </fieldset>
            </form>
        </p>
    </div>
<?php

            releaseLock( );
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
            $inputsQuery = "SELECT filename FROM $dbInputsTable WHERE type = 'bam'";

            $inputsResult = mysql_query( $inputsQuery ) or
                die( "Query '$inputsQuery' failed: " . mysql_error( ) );

            while( $row = mysql_fetch_array( $inputsResult, MYSQL_ASSOC ) )
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
                        <label>Chromosome length file</label>
                        <select name="tab_file">
<?php
            $inputsQuery = "SELECT filename FROM $dbInputsTable WHERE type = 'tab'";

            $inputsResult = mysql_query( $inputsQuery ) or
                die( "Query '$inputsQuery' failed: " . mysql_error( ) );

            while( $row = mysql_fetch_array( $inputsResult, MYSQL_ASSOC ) )
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
            $inputsQuery = "SELECT filename FROM $dbInputsTable WHERE type = 'gtf'";

            $inputsResult = mysql_query( $inputsQuery ) or
                die( "Query '$inputsQuery' failed: " . mysql_error( ) );

            while( $row = mysql_fetch_array( $inputsResult, MYSQL_ASSOC ) )
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
                        <input class="num" type="text" name="similarity" value="85" /> %
                    </p>
                    <p>
                        <label>Percentage sequence coverage</label>
                        <input class="num" type="text" name="coverage" value="55" /> %
                    </p>
                    <p>
                        <label>Gene names</label> <input type="text" name="genes" id="genes" />
                    </p>
                    <p>
                        <label>Email results to</label> <input type="text" name="email" id="email"
<?php
            $emailCookie = $_COOKIE[ 'seqgraph_email' ];
            if( $emailCookie != NULL )
                echo " value=\"$emailCookie\" ";
?>
                        />
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
