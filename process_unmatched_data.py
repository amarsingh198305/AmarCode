#!/usr/bin/python


#Purpose: Reactive Recon Process

#Change History:
#Version 1.0 - 20180226
#UPDATE - Made code change to only remove REJECTED messages for a specific DATE_ID - 20180327

#Version 1.1 - 20180509
#UPDATE - Changed Rejected Removal to use received_time vs sent_time



import base64
import getpass
import os
import socket
import sys
import traceback
from pymongo import MongoClient
import os,zipfile,datetime
import paramiko
from paramiko.py3compat import input
import ssl,csv
import ConfigParser
import MySQLdb
from datetime import datetime
from warnings import filterwarnings
filterwarnings('ignore', category = MySQLdb.Warning)
import fnmatch


#Check User Inputs
if len(sys.argv)<1:
   print "You did not include enough inputs"
   print "Example"+sys.argv[0]+" [working_dir]"
   print "Example"+sys.argv[0]+" /opt/company/RECON_TOOLS/UNMATCHED_MESSAGES/APAC/SMTP/2018-02-06"
   sys.exit()


## Global Variables

#Working Directory - This is crucial to be a fully qualified path because I use it to set global transport_type and date_id variables used in multiple places in the code
working_dir = sys.argv[1]
os.chdir(working_dir)
path_list = working_dir.split(os.sep)
transport_type=path_list[6]
date_id=path_list[7]


CHECK_TIME=datetime.now().strftime('%Y-%m-%d %H:%M:%S')


#####################################################################################################################################

def connectDB():
        db = MySQLdb.connect(host="localhost", user="opsuser", passwd="alcatraz1400", db="ALCATRAZ_METRICS")
        return db

#####################################################################################################################################

def CreateReconTable():
      #Create the mySQL database table to store the data we get from MongoDB
        cursor = global_db.cursor()

        sql="create TABLE IF NOT EXISTS UNMATCHED_MESSAGES ( \
         DATE_ID VARCHAR(1024) NOT NULL, \
         TRANSPORT_TYPE VARCHAR(1024) NOT NULL, \
         TRANSCRIPT_ID VARCHAR(2048) NOT NULL, \
         INTERACTION_ID VARCHAR(2048), \
         SENT_TIME DATETIME, \
         RECEIVED_TIME DATETIME, \
         PROCESSED_TIME DATETIME, \
         PROCESSING_STATE VARCHAR(1024) NOT NULL, \
         CLUSTER VARCHAR(1024) NOT NULL, \
         CHECK_TIME VARCHAR(1024) NOT NULL)"
        cursor.execute(sql)
        global_db.commit()

#####################################################################################################################################

def CleanReconTable(DATE_ID,TRANSPORT_TYPE):
    #Remove any pre-existing data for this DATE_ID and TRANSPORT_TYPE ( i.e. HTTP,SMTP )
        cursor = global_db.cursor()
        sql="delete from UNMATCHED_MESSAGES where DATE_ID='"+DATE_ID+"' and TRANSPORT_TYPE='"+TRANSPORT_TYPE+"'"
        print "DEBUG: "+sql
        cursor.execute(sql) 
        global_db.commit()

#####################################################################################################################################

def QueryUnmatchedData(trans_id):
     #Query MongoDB for provided TranscriptID
        unmatched_data=db.archive_metrics.find({"transcript_id":trans_id},{"transcript_id":1,"inter_id":1,"sent_time":1,"received_time":1,"processed_time":1,"processing_state":1,"cluster":1})

       #Check if there is an entry in ARCHIVE_METRICS - if it is not in ARCHIVE_METRICS on MongoDB then it is a NOT_FOUND Message
        if unmatched_data.count() != 0:
            InsertUnmatchedData(unmatched_data)
        else:
            InsertNotFoundData(trans_id)


#####################################################################################################################################

def ReadUnmatchedData(directory):
      #Gather all CSV files in a directory, read their contents, and call QueryUnmatchedData for each entry

        for file in os.listdir(directory):
            if file.endswith(".csv"):
                 full_path=os.path.join(directory, file)
                 print "DEBUG: "+full_path
                 ifile = open(full_path, "r")
                 for line in ifile:
                     #print "DEBUG: "+line.strip()
                     QueryUnmatchedData(line.strip())

#####################################################################################################################################

def InsertUnmatchedData(data):
      #Insert Unmtached Data provided, into the mySQL Database

        for result_set in data:
            cursor = global_db.cursor()
            transcript_id = result_set.get('transcript_id','')
            interaction_id = result_set.get('inter_id', '')
            sent_time = result_set.get('sent_time', '1979-01-01 00:00:00')
            received_time = result_set.get('received_time', '1979-01-01 00:00:00')
            processed_time = result_set.get('processed_time', '1979-01-01 00:00:00')
            processing_state = result_set.get('processing_state', 'NOT_FOUND')
            cluster = result_set.get('cluster', 'NO_CLUSTER')
            cursor.execute('''insert into UNMATCHED_MESSAGES (DATE_ID, TRANSPORT_TYPE, TRANSCRIPT_ID, INTERACTION_ID, SENT_TIME, RECEIVED_TIME, PROCESSED_TIME, PROCESSING_STATE, CLUSTER, CHECK_TIME) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''', (date_id, transport_type, transcript_id, interaction_id, sent_time, received_time, processed_time, processing_state, cluster, CHECK_TIME))
            global_db.commit()


#####################################################################################################################################

def InsertNotFoundData(transcript_id):
    #Insert TranscriptID with NOT_FOUND Status and dummy defaults into mySQL DB. 

        #print "DEBUG: Inserting Not Received for "+transcript_id
        cursor = global_db.cursor()
        interaction_id = 'null'
        sent_time = '1979-01-01 00:00:00'
        received_time = '1979-01-01 00:00:00'
        processed_time = '1979-01-01 00:00:00'
        processing_state = 'Not_Received'
        cluster = 'Not_Received'
        cursor.execute('''insert into UNMATCHED_MESSAGES (DATE_ID, TRANSPORT_TYPE, TRANSCRIPT_ID, INTERACTION_ID, SENT_TIME, RECEIVED_TIME, PROCESSED_TIME, PROCESSING_STATE, CLUSTER, CHECK_TIME) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''', (date_id, transport_type, transcript_id, interaction_id, sent_time, received_time, processed_time, processing_state, cluster, CHECK_TIME))
        global_db.commit()


#####################################################################################################################################

def FindInvalidRecords():
      #Remove all Rejected, Duplicate, Failed, Fatal reoordes that have a corresponding Archived message with the same transcriptID

      #Query for all Rejected, Duplicate, Failed, Fatal messages already in the mySQL table, find ones that also have an "Archived" entry and remove their Rejected, Duplicate, Failed, Fatal counterparts
        cursor = global_db.cursor()
        sql="select distinct transcript_id FROM UNMATCHED_MESSAGES where processing_state in ('Rejected','Duplicate','Fatal','Failed')"
        cursor.execute(sql)
        results = cursor.fetchall()
        for record in results:
            transcript_id=record[0]
            sql="select transcript_id FROM UNMATCHED_MESSAGES where processing_state='Archived' and transcript_id='"+transcript_id+"'"
            cursor.execute(sql)
            invalid_records = cursor.fetchall()
            for invalid_message in invalid_records:
                RemoveInvalidRecord(invalid_message[0])
        global_db.commit()


#####################################################################################################################################

def RemoveInvalidRecord(transcript_id):
    #Remove Record from mySQL DB
        print "DEBUG: Removing Invalid and Duplicate Records "+transcript_id
        cursor = global_db.cursor()
        sql="delete FROM UNMATCHED_MESSAGES where processing_state in ('Rejected','Duplicate','Fatal','Failed') and transcript_id='"+transcript_id+"'"
        cursor.execute(sql)
        global_db.commit()

#####################################################################################################################################

def FindExtraRejections():
      #Remove all Rejected records that have multiple entries but DO NOT have a corresponding Archived message with the same transcriptID

      #Query for all Rejected messages already in the mySQL table, find all duplicate enties and remove all but the oldest one
        cursor = global_db.cursor()
        sql="select distinct transcript_id FROM UNMATCHED_MESSAGES where processing_state in ('Rejected') and DATE_ID='"+date_id+"'"
        cursor.execute(sql)
        results = cursor.fetchall()
        for record in results:
            transcript_id=record[0]
            RemoveExtraRejections(transcript_id)
        global_db.commit()
#####################################################################################################################################

def RemoveExtraRejections(transcript_id):
      #Remove all Rejected records that have multiple entries but DO NOT have a corresponding Archived message with the same transcriptID

      #Query for all Rejected messages already in the mySQL table, find all duplicate enties and remove all but the oldest one
        cursor = global_db.cursor()
        sql="select distinct transcript_id, received_time FROM UNMATCHED_MESSAGES where processing_state in ('Rejected') and transcript_id='"+transcript_id+"' order by sent_time desc limit 1"
        cursor.execute(sql)
        results = cursor.fetchall()
        for record in results:
            transcript_id=record[0]
            received_time=record[1]
            print received_time
            sql="delete FROM UNMATCHED_MESSAGES where processing_state='Rejected' and transcript_id='"+transcript_id+"' and received_time !='"+str(received_time)+"'"
            print sql
            cursor.execute(sql)
        global_db.commit()


#####################################################################################################################################




######## MAIN ##############

if __name__ == "__main__":
        #Reading config values from config.properties
        Config = ConfigParser.ConfigParser()
        Config.read(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'unmatched.properties'))
        DBPORT = Config.getint("main","DBPORT")
        DBHOST = Config.get("main","DBHOST")
        SSL = Config.getboolean("main","SSL")
        AUTH = Config.getboolean("main","AUTH")
        MONGO_USER = Config.get("main","MONGO_USER")
        MONGO_PASSWORD = Config.get("main","MONGO_PASSWORD")
        DBNAME = Config.get("main","DBNAME")
        INSTANCEID = Config.get("main","INSTANCEID")
        LOCALDIR = Config.get("main",'LOCALDIR')

        unmatched_file="UNMATCHED"+Config.get("main","INSTANCEID")+".csv"
        try:
        #Connecting Mongo Servers and Database
                adb = MongoClient(DBHOST,DBPORT,ssl=SSL,ssl_cert_reqs=ssl.CERT_NONE)
                if AUTH:
                        adb.the_database.authenticate(MONGO_USER, MONGO_PASSWORD, mechanism='SCRAM-SHA-1',source='admin')
                db=adb[DBNAME]
        except Exception, e:
                print "Error While connecting to Mongo DB"+str(e)

        #CreateUnmatchedFile(unmatched_file,unmatched_data,LOCALDIR)
        global_db=connectDB()
        CreateReconTable()
        CleanReconTable(date_id, transport_type)
        ReadUnmatchedData(working_dir)
        FindInvalidRecords()
        FindExtraRejections()
        global_db.close()

