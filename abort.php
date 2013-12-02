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
    <form>
        <div id="abort">
            <p>
                <fieldset>
                    <legend>Abort</legend>
<?php
    if( $db = openDatabase( ) )
    {
        $job    = $_GET[ 'job' ];
        $delete = $_GET[ 'delete' ];

        if( $job != NULL )
        {
            if( $delete == 1 )
            {
                // Delete job
                $query = "DELETE FROM $dbJobsTable WHERE id = '$job'";
                $result = mysql_query( $query ) or
                    die( "Query '$query' failed: " . mysql_error( ) );

                echo "<p>Job $job deleted</p>\n";
                echo "<a href=\"results.php\">Back</a>\n";
            }
            else
            {
                // Abort job
                $query = "UPDATE $dbJobsTable SET abort = '1' WHERE id = '$job'";
                $result = mysql_query( $query ) or
                    die( "Query '$query' failed: " . mysql_error( ) );

                echo "<p>Job $job aborted</p>\n";
                echo "<a href=\"results.php?job=$job\">Back</a>\n";
            }
        }
        else
        {
            echo "No job number supplied\n";
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
</body>
</html>
