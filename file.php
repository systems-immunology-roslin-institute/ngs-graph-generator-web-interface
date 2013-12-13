<?php
    include( "shared.php" );

    if( $db = openDatabase( ) )
    {
        $fileId = isset($_GET[ 'fileId' ]) ? $_GET[ 'fileId' ] : NULL;
        $jobId = isset($_GET[ 'jobId' ]) ? $_GET[ 'jobId' ] : NULL;

        if( $fileId != NULL && $jobId != NULL )
        {
            $query = "SELECT filename FROM $dbResultsTable WHERE id = '$fileId'";

            // Run query to get the total number of rows
            $result = mysql_query( $query ) or
                die( "Query '$query' failed: " . mysql_error( ) );

            if( $result && mysql_num_rows( $result ) == 1 )
            {
                $row = mysql_fetch_array( $result, MYSQL_ASSOC );
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

                include( $fqFilename );
            }
        }

        closeDatabase( $db );
    }
?>
