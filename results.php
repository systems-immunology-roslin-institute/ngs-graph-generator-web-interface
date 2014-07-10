<?php
    include( "shared.php" );
?>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
    <title>NGS graph generator</title>
    <link rel="stylesheet" type="text/css" href="style.css">
</head>

<body>
    <div class="headerfooter">
        <div class="header">NGS graph generator</div>
        <a href=".">Scheduler</a>
        <a href="results.php">Results</a>
    </div>
<?php
    function compareFilenames( $a, $b )
    {
        $fileA = $a[ 'filename' ];
        $fileB = $b[ 'filename' ];
        $extA = pathinfo( $fileA, PATHINFO_EXTENSION );
        $extB = pathinfo( $fileB, PATHINFO_EXTENSION );

        if( $extA == $extB )
            return $fileA > $fileB;
        else
            return $extA > $extB;
    }

    if( $db = openDatabase( ) )
    {
?>
    <form name="emailFilter" method="get" action="results.php">
        <div id="filter">
            <p>
                <fieldset class="outer" id="filter">
                    <legend>Filter</legend>
                    <p>
                        <a class="button" href="results.php">All results</a>
                        <a class="button" href="results.php?inprogress=1">In progress</a>
                        <select name="email" onchange="emailFilter.submit( )">
                            <option value="">No filter</option>
<?php
        $query = "SELECT DISTINCT email FROM $dbJobsTable ORDER BY email";

        $result = mysql_query( $query ) or
            die( "Query '$query' failed: " . mysql_error( ) );

        while( $row = mysql_fetch_array( $result, MYSQL_ASSOC ) )
        {
            $email = $row[ 'email' ];

            if( $_GET[ 'email' ] == $email )
                echo "            <option value=\"$email\" selected>$email</option>\n";
            else
                echo "            <option value=\"$email\">$email</option>\n";
        }

        mysql_free_result( $result );
?>
                        </select>
                    </p>
                    <noscript>
                        <input type="submit" value="Filter by owner" />
                    </noscript>
                </fieldset>
            </p>
        </div>
        <div id="results">
            <p>
                <fieldset class="results">
                    <legend>Results</legend>
<?php
        $job        = isset($_GET[ 'job' ]) ? $_GET[ 'job' ] : NULL;
        $inprogress = isset($_GET[ 'inprogress' ]) ? $_GET[ 'inprogress' ] : NULL;
        $email      = isset($_GET[ 'email' ]) ? $_GET[ 'email' ] : NULL;

        $query = "SELECT " .
                        "$dbJobsTable.id, " .
                        "$dbJobsTable.arguments, " .
                        "$dbJobsTable.timequeued, " .
                        "$dbJobsTable.timestarted, " .
                        "$dbJobsTable.timefinished, " .
                        "$dbJobsTable.exitcode, " .
                        "$dbJobsTable.email, " .
                        "$dbJobsTable.abort " .
                        "FROM $dbJobsTable";

        if( $job != NULL )
        {
            $title = "Job $job";
            $query = $query . " WHERE id = '$job'";

            $abortQuery = "SELECT id FROM $dbJobsTable " .
                          "WHERE timefinished = '0'";

            $result = mysql_query( $abortQuery ) or
                die( "Query '$jobQuery' failed: " . mysql_error( ) );

            // Abort
            if( mysql_num_rows( $result ) > 0 )
            {
                $links = $links . "<a class=\"button\"" .
                    " href=\"abort.php?job=$job\">Abort</a>\n";
            }
        }
        else if( $inprogress != NULL )
        {
            $title = "In progress";
            $query = $query . " WHERE timefinished = '0'";
        }
        else if( $email != NULL )
        {
            $title = "Owned by $email";
            $query = $query . " WHERE email = '$email'";

            $jobQuery = "SELECT id FROM $dbJobsTable " .
                        "WHERE email = '$email' ORDER BY id";

            $result = mysql_query( $jobQuery ) or
                die( "Query '$jobQuery' failed: " . mysql_error( ) );

            $links = "Jobs: ";
            while( $row = mysql_fetch_array( $result, MYSQL_ASSOC ) )
            {
                $links = $links . "<a class=\"button\"" .
                    " href=\"results.php?job=" . $row[ 'id' ] . "\">" .
                    $row[ 'id' ] . "</a> ";
            }
            mysql_free_result( $result );
        }
        else
            $title = "All ";

        $query = $query . " ORDER BY timequeued DESC, resultsdir ASC ";

        // Run query to get the total number of rows
        $result = mysql_query( $query ) or
            die( "Query '$query' failed: " . mysql_error( ) );
        $totalRows = mysql_num_rows( $result );

        $url = "results.php?";
        if( $job != NULL )
            $url = $url . "job=$job&";
        if( $email != NULL )
            $url = $url . "email=" . urlencode( $email ) . "&";
        if( $inprogress != NULL )
            $url = $url . "inprogress=$inprogress&";

        if( $result && mysql_num_rows( $result ) > 0 )
        {
            echo "<table id=\"results_table\">\n";
            echo "<thead>\n";
            echo "<tr>\n";
            echo "<th>ID</th>";
            echo "<th>Owner</th>";
            echo "<th>Arguments</th><th>Time queued</th>" .
                 "<th>Processing time</th><th>Result</th>\n";
            echo "</tr>\n";
            echo "</thead>\n";
            echo "<tbody>\n";
            while( ( $row = mysql_fetch_array( $result, MYSQL_ASSOC ) ) )
            {
                $jobId              = $row[ 'id' ];
                $arguments          = $row[ 'arguments' ];
                $queued             = $row[ 'timequeued' ];
                $started            = $row[ 'timestarted' ];
                $finished           = $row[ 'timefinished' ];
                $exitcode           = $row[ 'exitcode' ];
                $email              = $row[ 'email' ];
                $abort              = $row[ 'abort' ];

                echo "<tr>\n";
                echo "<td>$jobId</td>\n";
                echo "<td>$email</td>\n";

                if( $arguments != "" )
                    echo "<td>$arguments</td>\n";
                else
                    echo "<td>None</td>\n";

                // Date queued
                if( $queued > 0 )
                    echo "<td>" . date( "G:i d/m/Y", $queued ) . "</td>\n";
                else
                    echo "<td></td>\n";

                if( $started > 0 )
                {
                    if( $finished > 0 )
                        $seconds = ( $finished - $started );
                    else
                        $seconds = ( time( ) - $started );

                    // Believe it or not, this is an integer divide
                    $hours      = ( $seconds - ( $seconds % 3600 ) ) / 3600;
                    $seconds    = $seconds % 3600;
                    $minutes    = ( $seconds - ( $seconds % 60 ) ) / 60;
                    $seconds    = $seconds % 60;
                    $seconds    = str_pad( $seconds, 2, "0", STR_PAD_LEFT );

                    if( $hours > 0 )
                    {
                        $minutes = str_pad( $minutes, 2, "0", STR_PAD_LEFT );
                        $duration = "$hours:$minutes:$seconds";
                    }
                    else
                    {
                        $duration = "$minutes:$seconds";
                    }

                    if( $exitcode == 0 )
                        echo "<td class=\"success\">";
                    else
                        echo "<td class=\"failure\">";

                    echo "<a href=\"output.php?id=$jobId\">$duration</a></td>\n";

                    if( $abort )
                        echo "<td>Aborted</td>\n";
                    else if( $finished > 0 )
                    {
                        if( $exitcode == 0 )
                        {
                            $fileLinks = "";

                            $resultsQuery = "SELECT id, filename FROM $dbResultsTable " .
                                "WHERE jobid = '$jobId' ORDER BY filename";

                            $resultsResult = mysql_query( $resultsQuery ) or
                                die( "Query '$resultsQuery' failed: " . mysql_error( ) );

                            if( mysql_num_rows( $resultsResult ) > 0 )
                            {
                                $files = array();
                                while( $row = mysql_fetch_array( $resultsResult, MYSQL_ASSOC ) )
                                    $files[] = array( 'id' => $row[ 'id' ], 'filename' => $row[ 'filename' ] );
                                mysql_free_result( $resultsResult );

                                usort( $files, 'compareFilenames' );

                                foreach( $files as $file )
                                {
                                    $id = $file[ 'id' ];
                                    $filename = $file[ 'filename' ];
                                    $ext = pathinfo( $filename, PATHINFO_EXTENSION );

                                    if( $ext == "zip" )
                                    {
                                        $linkClass = "zip";
                                    }
                                    else
                                    {
                                        $linkClass = "";
                                    }

                                    $fileLinks = $fileLinks .
                                        "<a class=\"$linkClass\" href=\"file.php?fileId=$id&jobId=$jobId\">$filename</a> ";
                                }

                                echo "<td>$fileLinks</td>\n";
                            }
                            else
                            {
                                echo "<td>No results</td>\n";
                            }
                        }
                        else
                        {
                            echo "<td>FAILED (exit code $exitcode)</td>\n";
                        }
                    }
                    else
                        echo "<td>" .
                                "<a class=\"button\" href=\"abort.php?job=$jobId\">Abort</a> " .
                                "<a class=\"button\" href=\"abort.php?job=$jobId&delete=1\">Delete</a>" .
                            "</td>\n";
                }
                else
                {
                    echo "<td>Not started</td>\n";
                }

                echo "</tr>\n";
            }
            echo "</tbody>\n";
            echo "</table>\n";

            mysql_free_result( $result );
        }
        else
        {
            echo "<p>No results</p>\n";
        }
?>
                </fieldset>
            </p>
        </div>
    </form>
<?php
        closeDatabase( $db );
    }
?>
    <div class="headerfooter footer"></div>
</body>
</html>
