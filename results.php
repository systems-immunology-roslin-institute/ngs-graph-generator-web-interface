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
        <a href=".">Create new job</a>
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

    function formatBytes($size, $precision = 2)
    {
        $suffixes = array('b', 'k', 'M', 'G', 'T');

        if( $size <= 0 )
            return "0" . $suffixes[0];

        $base = log($size) / log(1024);

        return round(pow(1024, $base - floor($base)), $precision) . $suffixes[floor($base)];
    }

    $token = isset($_GET[ 'token' ]) ? $_GET[ 'token' ] : NULL;

    if( $db = openDatabase( ) )
    {
?>
    <form name="emailFilter" method="get" action="results.php">
        <div id="filter">
            <p>
                <fieldset class="outer" id="filter">
                    <legend>Filter</legend>
                    <p>
<?php
    echo "<a class=\"button\" href=\"results.php?token=$token\">All results</a> ";
    echo "<a class=\"button\" href=\"results.php?inprogress=1&token=$token\">In progress</a>";
?>
                    </p>
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

    if( $token != NULL )
    {
        $queryText = "SELECT " .
                        "jobs.id, " .
                        "jobs.arguments, " .
                        "jobs.description, " .
                        "jobs.timequeued, " .
                        "jobs.timestarted, " .
                        "jobs.timefinished, " .
                        "jobs.exitcode, " .
                        "jobs.abort, " .
                        "jobs.size " .
                        "FROM jobs WHERE ";

        if( $job != NULL )
        {
            $queryText = $queryText . "id = ? AND ";
            $param = $job;
        }
        else if( $inprogress != NULL )
        {
            $queryText = $queryText . "timefinished = '0' AND ";
        }
        else
        {
            $queryText = $queryText . "validated = '1' AND ";
        }

        $queryText = $queryText . "token = ? ORDER BY timequeued DESC, resultsdir ASC";

        $query = $db->prepare( $queryText );

        if( $param )
            $query->bind_param( "ss", $param, $token );
        else
            $query->bind_param( "s", $token );

        // Run query to get the total number of rows
        $query->execute( )
            or die( "Query failed: " . $db->error );
        $result = $query->get_result( );
        $totalRows = $result->num_rows;

        if( $result && $totalRows > 0 )
        {
            echo "<table id=\"results_table\">\n";
            echo "<thead>\n";
            echo "<tr>\n";
            echo "<th>ID</th>";
            echo "<th>Description</th><th>Time queued</th>" .
                 "<th>Processing time</th><th>Result</th><th>Size</th>\n";
            echo "</tr>\n";
            echo "</thead>\n";
            echo "<tbody>\n";
            while( ( $row = $result->fetch_assoc( ) ) )
            {
                $jobId              = $row[ 'id' ];
                $arguments          = $row[ 'arguments' ];
                $description        = $row[ 'description' ];
                $queued             = $row[ 'timequeued' ];
                $started            = $row[ 'timestarted' ];
                $finished           = $row[ 'timefinished' ];
                $exitcode           = $row[ 'exitcode' ];
                $abort              = $row[ 'abort' ];
                $size               = $row[ 'size' ];

                echo "<tr>\n";
                echo "<td>$jobId</td>\n";

                if( $arguments != "" )
                    echo "<td>" . nl2br($description) . "</td>\n";
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

                            $resultsQuery = $db->prepare( "SELECT id, filename FROM results " .
                                "WHERE jobid = ? ORDER BY filename" );
                            $resultsQuery->bind_param( "s", $jobId );

                            $resultsQuery->execute( )
                                or die( "Query failed: " . $db->error );
                            $resultsResult = $resultsQuery->get_result( );

                            if( $resultsResult->num_rows > 0 )
                            {
                                $files = array();
                                while( $row = $resultsResult->fetch_assoc( ) )
                                    $files[] = array( 'id' => $row[ 'id' ], 'filename' => $row[ 'filename' ] );

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

                            $resultsQuery->close( );
                        }
                        else
                        {
                            echo "<td>FAILED (exit code $exitcode)</td>\n";
                        }
                    }
                    else
                    {
                        echo "<td>In progress</td>\n";
                    }

                    if( $size < 0 )
                        echo "<td>Unknown</td>\n";
                    else
                        echo "<td>" . formatBytes($size) . "</td>\n";
                }
                else
                {
                    echo "<td>Not started</td>\n";
                    if( $abort )
                        echo "<td>Aborted</td>\n";
                    else
                        echo "<td></td>\n";
                    echo "<td></td>\n";
                }

                echo "</tr>\n";
            }
            echo "</tbody>\n";
            echo "</table>\n";

        }
        else
        {
            echo "<p>No results</p>\n";
        }

        $query->close( );
    }
    else
    {
      echo "<p>Invalid/missing token</p>\n";
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
