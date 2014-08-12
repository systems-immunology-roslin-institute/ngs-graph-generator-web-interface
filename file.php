<?php
    include( "shared.php" );

    if( $db = openDatabase( ) )
    {
        $fileId = isset($_GET[ 'fileId' ]) ? $_GET[ 'fileId' ] : NULL;
        $jobId = isset($_GET[ 'jobId' ]) ? $_GET[ 'jobId' ] : NULL;

        if( $fileId != NULL && $jobId != NULL )
        {
            $query = $db->prepare( "SELECT filename FROM results WHERE id = ?" );
            $query->bind_param( "s", $fileId );

            $query->execute( )
                or die( "Query failed: " . $db->error );
            $result = $query->get_result( );

            if( $result && $result->num_rows == 1 )
            {
                $row = $result->fetch_assoc( );
                $filename = $row[ 'filename' ];
                mysql_free_result( $result );
                $outputDirectory = "/WWW/source/seq-graph.roslin.ed.ac.uk/output";
                $jobDirectory = "$outputDirectory/job-$jobId";
                $fqFilename = "$jobDirectory/$filename";

                header('Content-Description: File Transfer');
                header('Content-Type: application/octet-stream');
                header("Content-Disposition: attachment; filename=$filename");
                header('Content-Transfer-Encoding: binary');
                header('Expires: 0');
                header('Cache-Control: must-revalidate, post-check=0, pre-check=0');
                header('Pragma: public');
                header('Content-Length: ' . filesize($fqFilename));

                // Read it off in chunks as the alternative include
                // or file_get_contents methods exahust PHP memory limits
                $file = fopen($fqFilename, "r");
                while( !feof($file) )
                    echo fread($file, 16 * 1024 * 1024);
            }
        }

        closeDatabase( $db );
    }
?>
