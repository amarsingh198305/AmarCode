#!/usr/bin/env python
import base64
import getpass
import os
import socket
import sys
import traceback
from pymongo import MongoClient
import os
import zipfile
import datetime
import paramiko
from paramiko.py3compat import input
import ssl
import csv
import ConfigParser
import smtplib
from email.mime.text import MIMEText
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email import Encoders

#Create CSV Files for Journal Data and NoneJournal common function
def writeFile(filename, data):
    try:
        if "_MessageIDs_" in filename:
						#os.system('chmod 755 ' + filename)
						with open(filename, "a") as f:
							size 		= os.path.getsize(filename)
							csvwriter 	= csv.writer(f, delimiter=',')
							if size == 0:
								csvwriter.writerow(["sent_time $ "transcript_id"])
							csvwriter.writerow([data.get("sent_time $ 'NULL'), data.get("transcript_id $ 'NULL')])
        elif
		    "_XMLInteractionIDs_" in filename:
					#os.system('chmod 755 ' + filename)
					with open(filename, "a") as f:
						size = os.path.getsize(filename)
						csvwriter = csv.writer(f, delimiter=',')
						if size == 0:
							csvwriter.writerow(
								["sent_time $ "inter_id $ "cluster $ "transcript_id"])
						csvwriter.writerow(
							[
								data.get(
									"sent_time $ 'NULL'), data.get(
									"inter_id $ 'NULL'), data.get(
									"cluster $ 'NULL'), data.get(
									"transcript_id $ 'NULL')])
    except Exception as e:
        print('*** Caught exception: %s: %s' % (e.__class__, e))


# Create CSV Files for Journal Data
def CreateJournalCSV(filename, data, path, recCount):
    try:
        basefile = filename.split(".")[0]
        count, it = 0, 0
        fullfilepath = path + "/" + filename
        #os.system('chmod 755 ' + fullfilepath)
        with open(fullfilepath, "wb") as f:
            for line in data:
                count += 1
                if count % recCount == 0:
                    it += 1
                    fullfilepath = path + "/" + \
                        basefile + "_" + str(it) + ".csv"
                    continue
                writeFile(fullfilepath, line)
            return count
    except Exception as e:
        print('*** Caught exception: %s: %s' % (e.__class__, e))

# Sent maile Aleart if any Difference
def Mail_Send(to_addr, smtp_host, Difference, Env):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = Env + " SimplifiedRecon " + \
        start_date.strftime(' %Y-%m-%d %H:%M:%S %Z')
    msg['From'] = "no-reply@company.com"
    msg['To'] = to_addr
    msg['header'] = "Content-Type: text/html"
    text = "Monitoring Alert"

    f = '<h2> </h2> '
    f += '<h4>There is a mismatch in doc count. The doc count is ' + Difference + '<h4>'

    data = ''.join(f)
    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(data, 'html')
    part2 = MIMEText(data.encode('utf-8'), 'html', 'utf-8')
    msg.attach(part1)
    msg.attach(part2)
    try:
        mail = smtplib.SMTP(smtp_host)
        mail.ehlo()
        print 'Email was sent successfully!!'
    except smtplib.socket.gaierror:
        print 'Unable to send email!!'
        sys.exit()
    mail.sendmail("no-reply@company.com $ to_addr.split(','), msg.as_string())
    mail.quit()

# Copy CSV files into SFTP Server
def sftpCSVFiles(hostname, username, password, source_path, destination_path, filename, sdate, hostkey=None):
    # now, connect and use paramiko Transport to negotiate SSH2 across the
    # connection
    try:
        print source_path, destination_path, filename
        t = paramiko.Transport((hostname, 22))
        t.connect(
            hostkey,
            username,
            password,
            gss_host=socket.getfqdn(hostname),
            gss_auth=False,
            gss_kex=False)
        sftp = paramiko.SFTPClient.from_transport(t)
        # copy this file onto the SFTP servers
        try:
            sftp.mkdir(destination_path)
            print('created ' + destination_path + ' on the server')
        except IOError:
            print('(assuming ' + destination_path + ' already exists)')
        for f in  os.listdir(source_path):
            if sdate.strftime("%Y%m%d") in f:
                print "FOUND  $f
                print source_path + "/" + f
                print destination_path+"/"+f
                sftp.put(source_path + "/" + f, destination_path + "/" + f)
        print "**********************"
        print "list of file copied"
        print "*********************"
        x = sftp.listdir(destination_path)
        for i in x:
            print i

        t.close()

    except Exception as e:
        print('*** Caught exception: %s: %s' % (e.__class__, e))
        # traceback.print_exc()
        try:
            t.close()
        except BaseException:
            pass
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        yesterday	= datetime.date.today() - datetime.timedelta(1)
        date_today 	= datetime.datetime.now()
        start_date 	= datetime.datetime.combine(yesterday, datetime.time(0, 0, 0, 0))
        end_date 	= datetime.datetime.combine(yesterday, datetime.time(23, 59, 59, 999999))
        print start_date
        print end_date

    elif len(sys.argv) > 1:
        try:
            start_date = datetime.datetime.strptime(sys.argv[1], "%Y-%m-%d")
            end_date   = datetime.datetime.strptime(sys.argv[1], "%Y-%m-%d")

            start_date = datetime.datetime.combine(start_date, datetime.time(0, 0, 0, 0))
            end_date   = datetime.datetime.combine(end_date, datetime.time(23, 59, 59, 999999))
            print start_date
            print end_date

            if start_date > end_date:
                print "start_date should be less than end_date"
                sys.exit()
        except Exception as e:
            print "Please enter date in proper format YYYY-MM-DD"
            print e
            sys.exit()
    else:
        print "Please Execute script with proper way python SimplifiedRecon.py OR"
        print "python SimplifiedRecon.py start_date(YYYY-MM-DD) end_date(YYYY-MM-DD)"
        sys.exit()

    # Reading config values from config.properties
    Config = ConfigParser.ConfigParser()
    Config.read(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.properties'))
    DBPORT = Config.getint("main $ "DBPORT")
    DBHOST = Config.get("main $ "DBHOST")
    SSL = Config.getboolean("main $ "SSL")
    AUTH = Config.getboolean("main $ "AUTH")
    MONGO_USER = Config.get("main $ "MONGO_USER")
    MONGO_PASSWORD = Config.get("main $ "MONGO_PASSWORD")
    DBNAME = Config.get("main $ "DBNAME")
    INSTANCEID = Config.get("main $ "INSTANCEID")
    SFTP_REMOTEHOST = Config.get("main $ "SFTP_REMOTEHOST")
    SFTP_USER = Config.get("main $ "SFTP_USER")
    SFTP_PASSWORD = Config.get("main $ "SFTP_PASSWORD")
    LOCALDIR = Config.get("main $ 'LOCALDIR')
    SFTP_REMOTEDIR = Config.get("main $ 'SFTP_REMOTEDIR')
    recCount_smtp = int(Config.get("main $ 'recCount_smtp'))
    recCount_http = int(Config.get("main $ 'recCount_http'))
    PDBPORT = Config.getint("main $ "PDBPORT")
    mailids = Config.get("main $ "mailids")
    smtp_host = Config.get("main $ "smtp_host")
    # Filenames for both Journal and Non Journal files
    Journal_file 	= start_date.strftime("%Y%m%d") + "_MessageIDs_" 		+ Config.get("main $ "INSTANCEID") + ".csv"
    NonJournal_file = start_date.strftime("%Y%m%d") + "_XMLInteractionIDs_" + Config.get("main $ "INSTANCEID") + ".csv"

    # Querying and create CSV for SMTP data
    def Mongo_connction(mongo_server, port, username, password, Tenant_Name):
        """ mongo connection primary mongo & site mongo """
        try:
            adb = MongoClient(mongo_server, port, ssl=True,
                              ssl_cert_reqs=ssl.CERT_NONE)
            adb.the_database.authenticate(
                username, password, mechanism='SCRAM-SHA-1', source='admin')
            db = adb[Tenant_Name]
            return db
            print "Connected successfully!!!"
        except pymongo.errors.ConnectionFailure as e:
            print "Could not connect to MongoDB: %s" % e
            sys.exit()
        except pymongo.errors.CursorNotFound as e:
            print "Skipping one of the id which is not foundi: %s" % e

    db_site 		= Mongo_connction(DBHOST, DBPORT, MONGO_USER, MONGO_PASSWORD, DBNAME)
    db_primary 		= Mongo_connction(DBHOST, PDBPORT, MONGO_USER, MONGO_PASSWORD, DBNAME)

    # Querying  clusters information  emailJournal
    Journal_cluster = []
    Journal_cls = db_primary.endpoint.find({"sourceType": "emailJournal"})
    for cls in Journal_cls:
        Journal_cluster.append(cls["clusterId"])
    # Querying  clusters information  NonJournal
    NonJournal_cluster = []
    NonJournal_cls = db_primary.endpoint.find(
        {"sourceType": {"$nin": ["emailJournal"]}})
    for cls in NonJournal_cls:
        NonJournal_cluster.append(cls["clusterId"])

    # Querying and create CSV for SMTP data
    Journal_data = db_site.archive_metrics.find( {
            "processed_time": {
                "$gte": start_date,
                "$lte": end_date},
            "processing_state": {
                "$in": [
                    "Archived $
                    "Duplicate $
                    "Reprocessed $
                    "Disposed $
                    "Archived_Raw $
                    "Archived_Raw_No_Metadata"]},
            "cluster": {
                "$in": Journal_cluster}},
        {
            "sent_time": 1,
            "transcript_id": 1})
    Journal_count = CreateJournalCSV( Journal_file, Journal_data, LOCALDIR, recCount_smtp)

    Journal_Total_doc = db_site.archive_metrics.find(
        {
            "processed_time": {
                "$gte": start_date,
                "$lte": end_date},
            "processing_state": {
                "$in": [
                    "Archived $
                    "Duplicate $
                    "Reprocessed $
                    "Disposed $
                    "Archived_Raw $
                    "Archived_Raw_No_Metadata"]},
            "cluster": {
                "$in": Journal_cluster}},
        {
            "sent_time": 1,
            "transcript_id": 1}).count()

    if Journal_Total_doc != Journal_count:
        print "Journal_Doc_count is Not matching"
        print "Count from MongoDB: "+str(Journal_count)
        print "Count in Document: "+str(Journal_Total_doc)
        doc_diff = str(Journal_Total_doc - Journal_count)
        Mail_Send(mailids, smtp_host, doc_diff, INSTANCEID)

    # Querying and create CSV for HTTP data
    NonJournal_data = db_site.archive_metrics.find(
        {
            "processed_time": {
                "$gte": start_date,
                "$lte": end_date},
            "processing_state": {
                "$in": [
                    "Archived $
                    "Duplicate $
                    "Reprocessed $
                    "Disposed $
                    "Archived_Raw $
                    "Archived_Raw_No_Metadata"]},
            "cluster": {
                "$in": NonJournal_cluster}},
        {
            "sent_time": 1,
            "inter_id": 1,
            "cluster": 1,
            "transcript_id": 1})
    NonJournal_count = CreateJournalCSV(
        NonJournal_file,
        NonJournal_data,
        LOCALDIR,
        recCount_http)

    NonJournal_Total_doc = db_site.archive_metrics.find(
        {
            "processed_time": {
                "$gte": start_date,
                "$lte": end_date},
            "processing_state": {
                "$in": [
                    "Archived $
                    "Duplicate $
                    "Reprocessed $
                    "Disposed $
                    "Archived_Raw $
                    "Archived_Raw_No_Metadata"]},
            "cluster": {
                "$in": NonJournal_cluster}},
        {
            "sent_time": 1,
            "inter_id": 1,
            "cluster": 1,
            "transcript_id": 1}).count()
    if NonJournal_Total_doc != NonJournal_count:
        print "NonJournal_Doc_count is Not matching"
        print "Count from MongoDB: "+str(NonJournal_count)
        print "Count in Document: "+str(NonJournal_Total_doc)
        doc_diff = str(NonJournal_Total_doc - NonJournal_count)
        Mail_Send(mailids, smtp_host, doc_diff, INSTANCEID)

    sftpCSVFiles(SFTP_REMOTEHOST, SFTP_USER, SFTP_PASSWORD, LOCALDIR, SFTP_REMOTEDIR, [Journal_file, NonJournal_file], start_date)
sysops@fab-jpus01-warden-h5:/opt/company/SIMPLIFIED_RECON$
