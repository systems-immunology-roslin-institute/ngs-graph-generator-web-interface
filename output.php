<?php
    include( "shared.php" );

    if( $db = openDatabase( ) )
    {
        $id = isset($_GET[ 'id' ]) ? $_GET[ 'id' ] : NULL;

        if( $id != NULL )
        {
            $query = $db->prepare( "SELECT output FROM jobs WHERE id = ?" );
            $query->bind_param( "s", $id );

            $query->execute( )
                or die( "Query failed: " . $db->error );
            $result = $query->get_result( );

            if( $result && $result->num_rows == 1 )
            {
                $row = $result->fetch_assoc( );
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
