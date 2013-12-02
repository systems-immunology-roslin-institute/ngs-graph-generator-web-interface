<?php
    // Change these to match your setup
    $dbHost             = "localhost";
    $dbUser             = "root";
    $dbPassword         = "mysqlpass";
    $dbName             = "seq_graph";

    $dbSettingsTable    = "settings";
    $dbJobsTable        = "jobs";
    $dbResultsTable     = "results";
    $dbInputsTable      = "inputs";

    $viewWindow         = 10;

    function openDatabase( )
    {
        global  $dbHost;
        global  $dbUser;
        global  $dbPassword;
        global  $dbName;

        $db = mysql_connect( $dbHost, $dbUser, $dbPassword ) or
            die( "Could not connect: " . mysql_error( ) );

        if( $db )
            mysql_select_db( $dbName, $db );

        return $db;
    }

    function getSetting( $key )
    {
        global $dbSettingsTable;

        $query = "SELECT * FROM $dbSettingsTable WHERE setting = '$key'";
        $result = mysql_query( $query ) or
            die( "Query '$query' failed: " . mysql_error( ) );

        if( $result )
        {
            $row = mysql_fetch_array( $result, MYSQL_ASSOC );
            mysql_free_result( $result );

            return $row['value'];
        }
        else
            return "";
    }

    function closeDatabase( $db )
    {
        if( $db )
          mysql_close( $db );
    }
?>
