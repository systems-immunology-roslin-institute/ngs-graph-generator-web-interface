<?php
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

        $db = new mysqli( $dbHost, $dbUser,  $dbPass, $dbName );
        if( $db->connect_errno )
            die( "Could not connect: " . $db->connect_error );

        return $db;
    }

    function getSetting( $key )
    {
        global $dbSettingsTable;

        $db = openDatabase( );
        $query = $db->prepare( "SELECT * FROM settings WHERE setting = ?" );
        $query->bind_param( "s", $key );

        $query->execute( );
        $result = $query->get_result( );
        $value = "";

        if( $result )
        {
            $row = $result->fetch_assoc( );
            $value = $row['value'];
        }

        $query->close( );
        closeDatabase( $db );

        return $value;
    }

    function closeDatabase( $db )
    {
        $db->close( );
    }
?>
