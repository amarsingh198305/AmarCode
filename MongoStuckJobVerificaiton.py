#!/usr/bin/env python

#*********************************************************************************************************
# # This script alerts if queues is in queued running state from a given number of hours.
#*********************************************************************************************************
from pymongo import MongoClient, errors #3.7.2
import ssl
import sys
import os
import socket
import ConfigParser
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email import Encoders


def mongo_connection(host, port, user, passwd, tenant, auth):
    """ Connecting to Mongo """
    try:
         if auth == "true":
              adb = MongoClient(host, port, ssl=True, ssl_cert_reqs=ssl.CERT_NONE)
              adb.the_database.authenticate(user, passwd, mechanism='SCRAM-SHA-1', source='admin')
         else:
              adb = MongoClient(host, port)
         if not tenant in adb.database_names():
                 print ("Tenant \""+ str(tenant)+ "\"does NOT exist")
                 sys.exit()
         db = adb["alcatraz"]
         print (" \033[92m Connected to MongoDB successfully!!! \033[00m")
         return db
    except Exception as e:
            print ("\033[1;31mCould not connect to MongoDB \033[1;m")
            sys.exit()

def Mail_Send(From,to_addr, smtp_host, smtp_port, tenant_name, respance, Env, hours_before_last_run):
        now_date = datetime.datetime.now()
        msg = MIMEMultipart('alternative')
        msg['Subject'] =  Env + " - Jobs Stuck More Than " + str(hours_before_last_run) + " Hours - " + \
                now_date.strftime(' %Y-%m-%d %H:%M:%S %Z')
        msg['From'] = From
        msg['To'] = to_addr
        msg['header'] = "Content-Type: text/html"
        text = "Monitoring Alert"

        script_path = os.path.realpath(__file__)
        host_name, host_ip = get_Host_name_IP()
        path_string = host_name + "(" + host_ip + "):" + script_path

        html_begin = """
        <html>
        <body>
        <TH><TR><TD><b><h1 style="color:Tomato;">"""+ tenant_name.upper() +""": Jobs Stuck More Than """+ str(hours_before_last_run) + ' Hours' + """</h1></b></TD></TR></TH>
        <TABLE border=\"5\" cellspacing=\"1\" cellpadding=\"2\" width=\"55%\">
        <TR><TD><b>Job Name</b></TD><TD><b>Job ID</b></TD><TD><b>Tenant ID</b></TD><TD><b>Job Target</b></TD><TD><b>Job Status</b></TD> <TD><b>Job Sch Last Run Time</b></TD> <TD><b>Job Sch Next Run Time</b></TD><TD><b> Job Create Time</b></TD><TD><b>Job Update Time</b></TD></TR>"""

        for ids in respance:
                html_begin += """ <TR>"""
                for id in ids:
                     try:
			html_begin +="""<TD>"""+str(id)  +""" </TD>"""
		     except Exception as e:
			html_begin +="""<TD>"""+str(id.encode ( 'ascii', 'ignore' ))  +""" </TD>"""
                html_begin +="""</TR>"""
        html_begin +="""</table>
        <P>Note:- Above table monitor Shared and Sit MongoDB all active jobs in job_schedule collection If any jobs stuck for more than """ + str(hours_before_last_run)+ """ hours will get email notification.</P>
        <P>Origin of Alert: """ + str(path_string) +  """ </P>.
        </body></html>
        """

        data = ''.join(html_begin)
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(data, 'html')
        part2 = MIMEText(data.encode('utf-8'), 'html', 'utf-8')
        msg.attach(part1)
        msg.attach(part2)
        try:
            mail = smtplib.SMTP(smtp_host,smtp_port)
            mail.ehlo()
            mail.sendmail(From, to_addr.split(','), msg.as_string())

        except smtplib.socket.gaierror:
            print '\033[1;31mgaierror: Unable to send email!!\033[1;m'
            sys.exit()
        except:
            print('\033[1;31mUnable to send email!!\033[1;m')
            sys.exit()
        print ('\033[92m Email was sent successfully!! \033[00m')
        mail.quit()

def get_Host_name_IP():
        try:
                host_name = socket.gethostname()
                host_ip = socket.gethostbyname(host_name)
                return  host_name, host_ip
        except:
                print("Unable to get Hostname and IP")

if __name__ == "__main__":
        config = ConfigParser.ConfigParser()
        config.read("config.ini")
        host = config.get("mongo","host")
        Shared_port = config.getint("mongo","Shared_Port")
        Sit_port = config.getint("mongo","Sit_port")
        remot_port = config.getint("mongo","Remot_port")
        user = config.get("mongo","user")
        passwd = config.get("mongo","password")
        tenant = config.get("mongo", "tenant")
        auth = config.get("mongo", "auth")
        hours_before_last_run = config.getint("mongo", "hours_before_last_run")
        job_target_name = config.get("Not_Monitoring_jobs", "job_names").strip().split(",")
        From = config.get("email", "from")
        To = config.get("email", "to")
        smtp_host = config.get("smtp", "host")
        smtp_port = config.get("smtp", "port")
        Env = config.get("env", "Env")

        date_before_hours = datetime.datetime.utcnow() - datetime.timedelta(hours=hours_before_last_run) #ofsset for timezone
        shared_db= mongo_connection(host, Shared_port, user, passwd, tenant, auth)
        site_db= mongo_connection(host, Sit_port, user, passwd, tenant, auth)
        remot_db= mongo_connection(host, remot_port, user, passwd, tenant, auth)
        d = shared_db.tenancy.find({"_id": tenant})
        tenantuuid = ''
        for doc in d:
            tenantuuid = str(doc["tenantuuid"])
            Shar_dbc = shared_db["job_schedule"]
            Sit_dbc = site_db["job_schedule"]
            remot_dbc = remot_db["job_schedule"]
	    Shar_res = Shar_dbc.find({"tenantUUID" : tenantuuid, "job_active_fl":True, "job_status":{"$in":["RUNNING","QUEUED"]},"job_target":{"$nin":job_target_name},"job_sch_last_run_time": {"$lte":date_before_hours}})
			
		
	    Sit_res = Sit_dbc.find({"tenantUUID" : tenantuuid, "job_active_fl":True,"job_status": {"$in":["RUNNING","QUEUED"]},"job_target":{"$nin":job_target_name},"job_sch_last_run_time": {"$lte":date_before_hours}})


	    Remot_res = remot_dbc.find({"tenantUUID" : tenantuuid, "job_active_fl":True,"job_status": {"$in":["RUNNING","QUEUED"]},"job_target":{"$nin":job_target_name},"job_sch_last_run_time": {"$lte":date_before_hours}})

	    Job_ID=[]

	    for Shar_result in Shar_res:
		     if Shar_result["job_id"]:
				     Job_ID.append([Shar_result["job_name"],Shar_result["job_id"], Shar_result["tenantUUID"],Shar_result["job_target"],Shar_result["job_status"],Shar_result["job_sch_last_run_time"],Shar_result["job_sch_next_run_time"],Shar_result["job_create_time"],Shar_result["job_update_time"]])
		     else:
			      Job_ID.append(0)
	    for Sit_result in Sit_res:
		     if Sit_result["job_id"]:
				     Job_ID.append([Sit_result["job_name"],Sit_result["job_id"],Sit_result["tenantUUID"],Sit_result["job_target"],Sit_result["job_status"],Sit_result["job_sch_last_run_time"],Sit_result["job_sch_next_run_time"],Sit_result["job_create_time"],Sit_result["job_update_time"]])
		     else:
			      Job_ID.append(0)
	    for Remot_result in Remot_res:
		     if Remot_result["job_id"]:
				     Job_ID.append([Remot_result["job_name"],Remot_result["job_id"],Remot_result["tenantUUID"],Remot_result["job_target"],Remot_result["job_status"],Remot_result["job_sch_last_run_time"],Remot_result["job_sch_next_run_time"],Remot_result["job_create_time"],Remot_result["job_update_time"]])
		     else:
			      Job_ID.append(0)

            if len(Job_ID) == 0:
                 print "\033[92m INFO: No Job in QUEUED,RUNNING state from last " +str( hours_before_last_run) + " hours \033[00m"
                 sys.exit()
            else:
                 Mail_Send(From,To, smtp_host, smtp_port, tenant, Job_ID, Env, hours_before_last_run)
                 sys.exit()