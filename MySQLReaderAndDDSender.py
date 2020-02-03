#!/usr/bin/python

#*******************************************************************************************************************
# 

# This tool read data from mysql table `lag_drain_report_table` and send to datadog 
#
#
#*********************************************************************************************************************
import sys
import os
import MySQLdb
import datetime
import time
import argparse
import json
from time import gmtime, strftime
import telnetlib
import subprocess


parser = argparse.ArgumentParser()
parser.add_argument("--mysql_host", help="enter the mysql host",default="<hostsname>")
parser.add_argument("--mysql_port", help="enter the mysql port",default=3306)
parser.add_argument("--mysql_user", help="enter the mysql user name",default='<user>')
parser.add_argument("--mysql_pass", help="enter the mysql password name",default='<******>')
parser.add_argument("--mysql_db", help="enter the mysql datbase name",default='<database name>')
parser.add_argument("--mysql_table", help="enter the mysql table name",default='lag_drain_report_table')
parser.add_argument("--tenant_name", help="enter the tenant_name which enav",default='<tenant name>')
parser.add_argument("--ddhost", help="enter the DataDog host",default='localhost')
parser.add_argument("--ddport", help="enter the DataDog port",default=8125)
parser.add_argument("--environment", help="enter the DataDog Environment",default='Environment')

arg = parser.parse_args()
DB_HOST = arg.mysql_host
DB_PORT = arg.mysql_port
DB_USER = arg.mysql_user
DB_PASSWORD = arg.mysql_pass
DB_NAME = arg.mysql_db
DB_TABLE = arg.mysql_table
tenant_name = arg.tenant_name
dd_host = arg.ddhost
dd_port = arg.ddport
ENV = arg.environment

sites = ['primary', 'dr']



def get_maximum_monitoring_date(mysql_table_name):
    """
    get the maximum monitoring date for each table
    """

    query_max_monitoring_date = "select max(monitoring_date) as max_mon_date from {} where tenant_name = '{}'".format (
        mysql_table_name, tenant_name )
    result_max_monitoring_date = selectQuery ( DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME,
                                               query_max_monitoring_date )

    sql_mon_date_clause = ""
    max_mon_date = str ( result_max_monitoring_date[0]['max_mon_date'] )
    if len ( result_max_monitoring_date ) == 1:
        sql_mon_date_clause = " AND monitoring_date = '{}'".format ( max_mon_date )
    return sql_mon_date_clause, max_mon_date


def selectQuery(DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, query):
    
    connection = mysql_conncetion ( DB_HOST, int ( DB_PORT ), DB_USER, DB_PASSWORD, DB_NAME )
    cur = connection.cursor ( MySQLdb.cursors.DictCursor )
    try:
        cur.execute ( query )
        results = cur.fetchall ()
        connection.close ()
        return results
    except MySQLdb.Error as e:
        print "Error executing the query: " + str ( e )


def mysql_conncetion(mysql_host, mysql_port, mysql_user, mysql_password, mysql_db):
    """
    This fincetion conncetion to mysql databases;
    """
    try:
        conn = MySQLdb.connect (
            host=mysql_host,
            user=mysql_user,
            passwd=mysql_password,
            port=mysql_port,
            db=mysql_db
        )
        return conn
    except MySQLdb.Error as e:
        print ("ERROR IN CONNECTION '{}'".format ( e ))
        sys.exit ()

sql_mon_date_clause, max_mon_date = get_maximum_monitoring_date ( DB_TABLE )

query = """SELECT pipelines_report  as report FROM {}  WHERE monitoring_date= '{}' AND tenant_name = '{}';""".format(DB_TABLE, max_mon_date, tenant_name)


print (100*"*")

results = selectQuery ( DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, query )
counts = len ( results )

for row in results:
    pipelines_report = json.loads ( row['report'] )
    for site in sites:
        if site in pipelines_report.keys ():
            for key in pipelines_report[site].keys ():
                title = pipelines_report[site][key]['title'].replace ( " ", "_" )
                lag_value = pipelines_report[site][key]['lag']
		drain_rate =0
		try:
		    if 'status' in pipelines_report[site][key]["acked_stats"].keys():
			if pipelines_report[site][key]["acked_stats"].get('status', 'running').lower() == "not running":
			    row = pipelines_report[site][key]["acked_stats"]['status'] 
		    else :
        		drain_rate = float(pipelines_report[site][key]["acked_stats"]["600"]['rate'])
		except KeyError as e:
		    print ("ERROR: acked_stats key is not found for {}. Please check lag_report for any Error for {} pipeline data").format(key, key)
                #LAG_VALUE_COMMAND = 'echo "custom.{}.LAG_REPORT.PIPELINE_LAG.{}:{}|g"| nc -4u -w1 {} {}'.format(ENV,title, lag_value,dd_host,dd_port)
                #DRAIN_RATE_COMMAND = 'echo "custom.{}.LAG_REPORT.PIPELINE_RATE.{}:{}|g"|nc -4u -w1 {} {}'.format(ENV,title,drain_rate,dd_host,dd_port)
		# Use Kyle's new naming convention
                LAG_VALUE_COMMAND2 = 'echo "smarsh.ingestion.pipeline_lag.{}:{}|g||#metric_tag:{}" | nc -4u -w1 {} {}'.format(title, lag_value,ENV,dd_host,dd_port)
                DRAIN_RATE_COMMAND2 = 'echo "smarsh.ingestion.pipeline_rate.{}:{}|g||#metric_tag:{}" | nc -4u -w1 {} {}'.format(title,drain_rate,ENV,dd_host,dd_port)
	
                #print LAG_VALUE_COMMAND
	        #print DRAIN_RATE_COMMAND
                print LAG_VALUE_COMMAND2
	        print DRAIN_RATE_COMMAND2

		# below command uncomment data sending to datadog
                #subprocess.call(LAG_VALUE_COMMAND,shell=True)
                #subprocess.call(DRAIN_RATE_COMMAND,shell=True)

                subprocess.call(LAG_VALUE_COMMAND2,shell=True)
                subprocess.call(DRAIN_RATE_COMMAND2,shell=True)
print
print (100*"*")
