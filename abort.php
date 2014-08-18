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
    <form>
        <div id="abort">
            <p>
                <fieldset>
                    <legend>Abort</legend>
<?php
    if( $db = openDatabase( ) )
    {
        $job     = $_GET[ 'job' ];
        $confirm = $_GET[ 'confirm' ];
        $token   = $_GET[ 'token' ];

        if( $confirm == NULL )
        {
            $query = $db->prepare( "SELECT id FROM jobs WHERE id = ? AND token = ? AND timefinished != '0'" );
            $query->bind_param( "ss", $job, $token );

            $query->execute( )
                or die( "Query failed: " . $db->error );

            $result = $query->get_result( );
            $alreadyAborted = ( $result->num_rows > 0 );

            if( $alreadyAborted )
            {
                echo "<p><a href=\"results.php?job=$job\">Job $job</a> already finished</p>\n";
                echo "<a href=\"results.php?job=$job\">Back</a>\n";
            }
            else
            {
                echo "<p>Abort job $job?</p>\n";
                echo "<a href=\"" . $_SERVER[REQUEST_URI] . "&confirm=1\">Yes</a>\n";
                echo "<a href=\"results.php?job=$job\">No</a>\n";
            }
        }
        else if( $job != NULL )
        {
            // Abort job
            $query = $db->prepare( "UPDATE jobs SET abort = '1' WHERE id = ? AND token = ? AND timefinished = '0'" );
            $query->bind_param( "ss", $job, $token );
            $query->execute( )
                or die( "Query failed: " . $db->error );
            $result = $query->get_result( );

            if( $query->affected_rows > 0 )
            {
                echo "<p>Job $job aborted</p>\n";
                echo "<a href=\"results.php?job=$job\">Back</a>\n";
            }
            else
            {
                echo "<p>Could not abort job $job</p>\n";
                echo "<a href=\"results.php?job=$job\">Back</a>\n";
            }
        }
        else
        {
            echo "No job number supplied\n";
        }

        closeDatabase( $db );
    }
?>
                </fieldset>
            </p>
        </div>
    </form>
</body>
</html>
