<?php
    include( "shared.php" );

    if( $db = openDatabase( ) )
    {
        $id = isset($_GET[ 'id' ]) ? $_GET[ 'id' ] : NULL;

        if( $id != NULL )
        {
            $query = "SELECT output FROM $dbJobsTable WHERE id = '$id'";

            // Run query to get the total number of rows
            $result = mysql_query( $query ) or
                die( "Query '$query' failed: " . mysql_error( ) );

            if( $result && mysql_num_rows( $result ) == 1 )
            {
                $row = mysql_fetch_array( $result, MYSQL_ASSOC );
                $output = $row[ 'output' ];

                header('Content-Type: text/plain');
                header('Expires: 0');
                header('Cache-Control: must-revalidate, post-check=0, pre-check=0');
                header('Pragma: public');

                echo $output;
            }
        }

        closeDatabase( $db );
    }
?>
