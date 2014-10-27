Web Interface for the Next Generation Sequencing Graph Generator
================================================================

This is a web frontend for the Next Generation Sequencing Graph Generator. It consists of a web site authored in rudimentary PHP and HTML, together with a Python daemon whose responsibility it is to execute the jobs as created on the web site. The system requires a MySQL database to which access is configured via the file dbSettings.json. See the dbSettings.json.example file for sample contents. Executing job-daemon.py will create the required tables if they don't already exist, but further supplmentary settings must be provided in order to suit the installation environment. These settings are made via a MySQL command line or via an SQL script such as the supplied init.sql.

Prerequisites
-------------

* Python
* PHP
* MySQL

Authors
-------

* Tim Angus
