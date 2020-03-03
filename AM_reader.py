sysops@fab-emea01-warden-h1:/opt/actiance/Internal_C3_DHC_EGW_RAW$ cat Archive_Egw_Raw_Eml.py
#!usr/bin/python

# *****************************************************************************************************
# This generates Egw raw Eml transcript IDs and count from ES Archive Metrics collection
#
# Updated date 29-03-2019
#
# ****************************************************************************************************
# Required modules
import datetime
import time
import ConfigParser
import smtplib
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.MIMEBase import MIMEBase
from email import Encoders
import urllib2
import atexit
import sys
import pytz
import json
import os
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from hurry.filesize import size, si
import csv
import tempfile

# Configer detiles
Config = ConfigParser.ConfigParser()
Config.read("config.ini")
host = Config.get('es', 'essr_host')
port = Config.get('es', 'port')
tenant = Config.get('es', 'tenant')
user = Config.get('es', 'user')
passwd = Config.get('es', 'passwd')
Env = Config.get('environment', 'Env')
smtp_host = Config.get('smtp', 'host')
From = Config.get('email', 'from')
to = Config.get('email', 'to')

print"----------------------------------------------------------------------------------------------------------------"
# Date &time  stamp

local_tz = pytz.timezone("America/Los_Angeles")

date_today 	= datetime.datetime.now()
yesterday 	= datetime.date.today() - datetime.timedelta(1)
start_date 	= datetime.datetime.combine(yesterday, datetime.time(0, 0, 0, 0))
end_date	= datetime.datetime.combine(yesterday, datetime.time(23, 59, 59, 999999))


# print start_date, end_date


def date_time(how_many_start, how_many_end):
    """ date time return in this funcetion """
    date_today 		= datetime.datetime.now()
    date 			= date_today.replace(hour=00, minute=00, second=00, microsecond=0)
    end_date     	= date - datetime.timedelta(days=how_many_end)
    start_date     	= date - datetime.timedelta(days=how_many_start)
    es_start_date  	= start_date.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
    es_end_date 	= end_date.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
    return es_start_date, es_end_date


start_date_24, end_date24 								= date_time(1, 0)
start_date_7days, end_date_7days						 = date_time(7, 1)
start_date_Older_than1Week, end_date_Older_than1Week 	= date_time(14, 7)
start_date_Older_than2Weeks, end_date_Older_than2Weeks	 = date_time(21, 14)
start_date_Older_than3Weeks, end_date_Older_than3Weeks	 = date_time(28, 21)

d 			 = datetime.datetime.now()
st_old_4	 = (datetime.date(d.year, d.month, d.day) - datetime.date(2018, 03, 15)).days

start_date_Older_than4Weeks, end_date_Older_than4Weeks = date_time(st_old_4, 28)

datetime_with_tz = local_tz.localize(date_today, is_dst=None)  # No daylight saving time


def Elastic_Search(host, index):
    url1 = "https://" + host + ":9640/" + index + "_archive_metrics_*.av4/_search"

    return url1


es_urll = Elastic_Search(host, tenant)

// GET THE TRANSCRIPT IDS WHERE INTER_DATE_STATE IN ( ["Archived_Raw", "Gateway_Archived_Raw"] ) AND 
// "processing_state":"Archived"  and
// "received_time"  between Start date and end date            FOR  -  1,2,3,4 weeks buckets
def es_raw_data(url, user, passwd, start_date, end_date):
    Transcript_Id = []
    query = '{ "size": 9999, "query": { "bool": { "must": [ { "terms":' + \
            '{ "inter_data_state": ["Archived_Raw", "Gateway_Archived_Raw"] } } ,' \
            '{"term":{"processing_state":"Archived"}}, { "range": ' + \
            '{ "received_time":{ "gte": "' + start_date + '", ' + \
            '"lte": "' + end_date + '" } } } ] } } }'
    try:
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        resp = requests.post(url, auth=(user, passwd),
                             verify=False, data=query)
        data  = resp.json()
        total = data["hits"]["total"]
        datas = data["hits"]["hits"]
        for x in data["hits"]["hits"]:
            tid = x["_source"]["transcript_id"]
            Transcript_Id.append(tid)
        return total, datas, list(set(Transcript_Id))
    except requests.exceptions.ConnectionError:
        print "url" + url + " not reachable"
        sys.exit()


def es_raw_result(url, user, passwd, query):
    """ Connecting to ES and getting data """
    try:
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
        resp = requests.post(url, auth=(user, passwd),
                             verify=False, data=query)
        data = resp.json()
        return data
    except requests.exceptions.ConnectionError:
        print "url" + url + " not reachable"
        sys.exit()


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]


def add_list(datas):
    tids = []
    for data in datas:
        tid = data["_source"]["transcript_id"]
        tids.append(tid)
    return tids


def reprocess_count(url, user, passwd, start_date, end_date):
    rtranscript_id = []
    total, datas_1d, Transcript_Id = es_raw_data(url, user, passwd, start_date, end_date)
    tids = add_list(datas_1d)
    longlist = list(chunks(tids, 100))
    cnt = 0
    for tid in longlist:

        query = '{ "size": 9999, "query" : { "bool" : { "must" : ' + \
                ' [ { "terms" :{ "transcript_id" : ' + \
                ' ' + json.dumps([str(x) for x in tid]) + ' }},{"term":{"processing_state":"Archived"}}],' + \
                '"must_not": {"term": {"inter_data_state":"Gateway_Archived_Raw"}}, "should":[ { "terms" :' + \
                ' { "inter_data_state":["Gateway_Reprocessed","invalid coc hash received","archive_native"]}' + \
                '  }, { "missing": { "field": ' + \
                '"inter_data_state"}}], "minimum_should_match": 1' + \
                ' } } }'

        pdata = es_raw_result(url, user, passwd, query)
        arr2 = pdata["hits"]["hits"]
        for value in arr2:
            tidss = value["_source"]["transcript_id"]
            rtranscript_id.append(tidss)
        cnt = cnt + int(pdata["hits"]["total"])
        # below total Transcript_Id how_many reprocessed...
    Rtranscript_id = list(set(rtranscript_id))
    li_dif = [i for i in Transcript_Id + Rtranscript_id if i not in Transcript_Id or i not in Rtranscript_id]
    return len(li_dif) ,li_dif


Last_24h_Today_Count, last_24h_Today_Tids					 = reprocess_count(es_urll, user, passwd, start_date_24, end_date24)
Less_than_a_Week_Count, Less_than_a_Week_Tids 				= reprocess_count(es_urll, user, passwd, start_date_7days, end_date_7days)
Older_than_Week_Count, Older_than_Week_Tids			 		= reprocess_count(es_urll, user, passwd, start_date_Older_than1Week,end_date_Older_than1Week)
Older_than_two_Weeks_Count, Older_than_two_Weeks_Tids 		= reprocess_count(es_urll, user, passwd,start_date_Older_than2Weeks, end_date_Older_than2Weeks)
Older_than_three_Weeks_Count, Older_than_three_Weeks_Tids 	= reprocess_count(es_urll, user, passwd,start_date_Older_than3Weeks,end_date_Older_than3Weeks)
Older_than_four_Weeks_Count, Older_than_four_Weeks_Tids     = reprocess_count(es_urll, user, passwd,start_date_Older_than4Weeks,end_date_Older_than4Weeks)

Total_Eml = Last_24h_Today_Count + Less_than_a_Week_Count + Older_than_Week_Count + Older_than_two_Weeks_Count + \
            Older_than_three_Weeks_Count + Older_than_four_Weeks_Count


def SendReport(env, From, to, smtp_host):
    # Create message container - the correct MIME type is multipart/alternative.

    msg = MIMEMultipart('alternative')
    msg['Subject'] = env + " - Raw Counts and Transcript IDs"
    msg['From'] = From
    msg['To'] = to

    html_begin = """
        <html>
          <body>
          <TABLE border=\"5\" cellspacing=\"1\" cellpadding=\"2\" width=\"90%\">
          <TR><TD><b>Raw Type/Duration </b></TD><TD><b>New (Today)</b></TD><TD><b>Less than a Week</b>
          </TD><TD><b>Older than Week</b></TD><TD><b> Older than two Weeks</b></TD><TD>
          <b>Older than three Weeks</b></TD> <TD><b>Older than four Weeks</b></TD><TD><b>Total</b></TD></TR>
        """
    html_begin += "<TR><TD>" + "EGW Raw EML" + "</TD><TD>" + str(Last_24h_Today_Count) + "</TD><TD>" + str(
        Less_than_a_Week_Count) + "</TD><TD>" + str(Older_than_Week_Count) + "</TD><TD>" + str(
        Older_than_two_Weeks_Count) + "</TD><TD>" + str(Older_than_three_Weeks_Count) + "</TD><TD>" + str(
        Older_than_four_Weeks_Count) + "</TD><TD>" + str(Total_Eml) + "</TD></TR>"
    html_end = """</TABLE><br> """
    html_end1 = html_end2 = html_end3 = html_end4 = html_end5 = html_end6 = """ """

    if len(last_24h_Today_Tids) != 0:
        html_end1 = """ <TABLE> <TH> New (Today)</TH>"""
    if len(Less_than_a_Week_Tids) != 0:
        html_end2 = """<TABLE> <TH> Less than a Week </TH>"""
    if len(Older_than_Week_Tids) != 0:
        html_end3 = """ <TABLE> <TH> Older than Week </TH>"""
    if len(Older_than_two_Weeks_Tids) != 0:
        html_end4 = """ <TABLE> <TH> Older than two Weeks </TH>"""
    if len(Older_than_three_Weeks_Tids) != 0:
        html_end5 = """<TABLE> <TH> Older than three Weeks </TH>"""
    if len(Older_than_four_Weeks_Tids) != 0:
        html_end6 = """ <TABLE> <TH> Older than four Weeks </TH>"""

    for cnt, value in enumerate(sorted(last_24h_Today_Tids)):
        html_end1 += """ <TR><TD>""" + str(value) + """<br></TR></TD>"""
    html_end1 += """</TABLE><br>"""
    for cnt, value in enumerate(sorted(Less_than_a_Week_Tids)):
        html_end2 += """<TR><TD>""" + str(value) + """<br></TD></TR>"""
    html_end2 += """</TABLE><br>"""
    for cnt, value in enumerate(sorted(Older_than_Week_Tids)):
        html_end3 += """<TR><TD>""" + str(value) + """<br></TD></TR>"""
    html_end3 += """</TABLE><br>"""
    for cnt, value in enumerate(sorted(Older_than_two_Weeks_Tids)):
        html_end4 += """<TR><TD>""" + str(value) + """<br></TD></TR>"""
    html_end4 += """</TABLE><br>"""
    for cnt, value in enumerate(sorted(Older_than_three_Weeks_Tids)):
        html_end5 += """<TR><TD>""" + str(value) + """<br></TD></TR>"""
    html_end5 += """</TABLE><br>"""
    for cnt, value in enumerate(sorted(Older_than_four_Weeks_Tids)):
        html_end6 += """<TR><TD>""" + str(value) + """<br></TD></TR>"""
    html_end6 += """</TABLE><br>"""
    try:
        html_output_data = html_begin + html_end + html_end1 + html_end2 + html_end3 + html_end4 + html_end5 + html_end6
        part2 = MIMEText(html_output_data.encode('utf-8'), 'html', 'utf-8')
        msg.attach(part2)
        mail = smtplib.SMTP(smtp_host)
        mail.ehlo()
        print ('\033[1;32mEmail was sent successfully!!\033[1;m')
        mail.sendmail(From, to.split(','), msg.as_string())
        mail.quit()
        print (to.split(','))
    except smtplib.socket.gaierror:
        print ('\033[1;31mUnable to send email!!\033[1;m')
        sys.exit()


SendReport(Env, From, to, smtp_host)

sysops@fab-emea01-warden-h1:/opt/company/Internal_C3_DHC_EGW_RAW$
