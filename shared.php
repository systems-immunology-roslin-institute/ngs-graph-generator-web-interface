<?php
    $dbSettingsTable    = "settings";
    $dbJobsTable        = "jobs";
    $dbResultsTable     = "results";
    $dbInputsTable      = "inputs";

    function openDatabase( )
    {
        $scriptDirectory = realpath(dirname(__FILE__));
        $dbSettingsFile = $scriptDirectory . "/dbSettings.json";
        $dbSettingsData = file_get_contents($dbSettingsFile);
        $dbSettings = json_decode($dbSettingsData, true);

        $dbHost = $dbSettings['dbHost'];
        $dbUser = $dbSettings['dbUser'];
        $dbPass = $dbSettings['dbPass'];
        $dbName = $dbSettings['dbName'];

        $db = mysql_connect( $dbHost, $dbUser, $dbPass ) or
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
