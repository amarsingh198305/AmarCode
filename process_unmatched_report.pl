ASingh@fab-jpus01-warden-h5:/opt/actiance/RECON_TOOLS/MASTER_SCRIPTS$ cat process_unmatched_report.pl
#!/usr/bin/perl



use strict;
use DBI;
use POSIX;
use POSIX qw(strftime);


#Create Global Variables
my $WORKING_DIR="/opt/company/RECON_TOOLS/MASTER_SCRIPTS/REACTIVE_RECON";
my $mail_file="$WORKING_DIR/recon.mail.file";
#my $TO_EMAIL_ADDRESSES="afiaccone\@company.com";
my $TO_EMAIL_ADDRESSES="sre_app_services\@company.com,sre_alerts\@company.com ,RGopalan\@company.com, VAgarwal\@company.com, bkeeley\@company.com, rcompestine\@company.com, ktieu\@company.com, dsubramanyam\@company.com, jlittle\@company.com, blittle\@company.com, Stanley.Neel\@company.com,surendra.pattipati\@company.com";
my $ENVIRONMENT="NAM";
my $TODAY=strftime( '%b %e, %Y %H:%M:%S', localtime );

#Create Global DB Handles
my $dbhMetricsDB=connectDB("ALCATRAZ_METRICS","localhost","opsuser","alcatraz1400");

#Create Global Date Array
my %global_date_hash;
my @global_date_array=[];
my @global_SMTP_date_array=[];
my @global_HTTP_date_array=[];
$global_date_hash{'HTTP'}='@global_HTTP_date_array';
$global_date_hash{'SMTP'}='@global_SMTP_date_array';


####################################################################################################################################

sub connectDB {

 #Creates Oracle DB handle and returns it
  my $DBNAME=$_[0];
  my $DBHOST=$_[1];
  my $DBUSER=$_[2];
  my $DBPASS=$_[3];

  my $dbh = DBI->connect("DBI:mysql:$DBNAME:$DBHOST", "$DBUSER", "$DBPASS");
  $dbh or die "Could not connect: $!";
  return $dbh;

}

####################################################################################################################################

sub commify {
 #Takes in a number and returns a number with commas

    my $text = $_[0];
    $text=~ s/(\d)(?=(\d{3})+(\D|$))/$1\,/g;
    return "$text";
}

####################################################################################################################################

sub getDatesToProcess {

    #Queries UNMATCHED_MESSAGES for distinct dates, Query is done twice - once for HTTP and once for SMTP.
      my $transport_type=$_[0];
      my $DATE_ID;
      @global_date_array=[];

      my $sql="select distinct DATE_ID from UNMATCHED_MESSAGES where TRANSPORT_TYPE='$transport_type' order by DATE_ID desc";
                 my $sth = $dbhMetricsDB->prepare($sql);
                 $sth->execute();
                 $sth->bind_columns(\$DATE_ID);

            while ( $sth->fetch )
                 {
                   #print "DEBUG: Pushing $DATE_ID onto Global Date Array\n";
                   push @global_date_array,"$DATE_ID";

                 }
                 $sth->finish;
         #Set Array Values to global transport array
                 $global_date_hash{$transport_type}=\@global_date_array;

}

####################################################################################################################################

sub getCounts {

  #Query UNMATCHED_MESSAGES table looking looking for unmatched message categories and counts
      my $STATE=$_[0];
      my $TRANSPORT_TYPE=$_[1];
      my $DATE_ID=$_[2];
      my $COUNT;
      my $sql="";

   #Different Query is used for messages that are Archived vs those that are in any other state that is not considered archived
        if ( $STATE eq "Archived" )
                { $sql="select count(*) from UNMATCHED_MESSAGES where DATE_ID='$DATE_ID' and PROCESSING_STATE in ('Archived','Duplicate','Reprocessed','Disposed') and TRANSPORT_TYPE='$TRANSPORT_TYPE'"; }

        elsif ( $STATE eq "Archived_Raw" )
                { $sql="select count(*) from UNMATCHED_MESSAGES where DATE_ID='$DATE_ID' and PROCESSING_STATE in ('Archived_Raw','Archived_Raw_No_Metadata') and TRANSPORT_TYPE='$TRANSPORT_TYPE'"; }

        elsif ( $STATE eq "Queued" )
                { $sql="select count(*) from UNMATCHED_MESSAGES where DATE_ID='$DATE_ID' and PROCESSING_STATE in ('Queued','Reprocessing') and TRANSPORT_TYPE='$TRANSPORT_TYPE'"; }

        else
                {
                  $sql="select count(*) from UNMATCHED_MESSAGES where DATE_ID='$DATE_ID' and PROCESSING_STATE ='$STATE' and TRANSPORT_TYPE='$TRANSPORT_TYPE'";
                }

                #print "DEBUG: SQL $sql\n";

        my $sth = $dbhMetricsDB->prepare($sql);
        $sth->execute();
        my @results=$sth->fetchrow_array;

         if ( $results[0] ne "" )
            {
              my $result=$results[0];
              return $result;
            }
         else
            { return 0; }

        $sth->finish;

  }

####################################################################################################################################

sub processReport {

  #Create HTML Report with table full of unamtched data categorization that is color coded
  my $transport_type=$_[0];
  my $total_bgcolor="gray";

  my ($archived_count, $archived_raw_count, $queued_count, $not_received_count, $rejected_count, $fatal_count, $failed_count, $total_row_sum) = 0;
  my ($archived_column_sum, $archived_raw_column_sum, $queued_column_sum, $not_received_column_sum, $rejected_column_sum, $fatal_column_sum, $failed_column_sum, $total_column_sum) = 0;

  open MAIL_FILE, ">>", "$mail_file" or die $!;
  print MAIL_FILE "<TABLE border=\"4\" cellspacing=\"0\" cellpadding=\"1\" width=\"75%\">\n";

      print MAIL_FILE "<TR><TD align='center'><b>ENV/TRANSPORT</b></TD><TD align='center'><b>DATE</b></TD><TD align='center'><b>Archived</b></TD><TD align='center'><b>Archived_Raw</b></TD><TD align='center'><b>Queued</b></TD><TD align='center'><b>Not_Received</b></TD><TD align='center'><b>Rejected</b></TD><TD align='center'><b>Fatal</b></TD><TD align='center'><b>Failed</b></TD><TD align='center'><b>Total</b></TD></TR>";

          foreach my $date_id (@{$global_date_hash{"$transport_type"}})
           {
             if ($date_id =~ /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)
              {
                 $archived_count=getCounts("Archived","$transport_type","$date_id");
                 $archived_column_sum=$archived_column_sum + $archived_count;

                 $archived_raw_count=getCounts("Archived_Raw","$transport_type","$date_id");
                 $archived_raw_column_sum=$archived_raw_column_sum + $archived_raw_count;

                 $queued_count=getCounts("Queued","$transport_type","$date_id");
                 $queued_column_sum=$queued_column_sum + $queued_count;

                 $not_received_count=getCounts("Not_Received","$transport_type","$date_id");
                 $not_received_column_sum=$not_received_column_sum + $not_received_count;

                 $rejected_count=getCounts("Rejected","$transport_type","$date_id");
                 $rejected_column_sum=$rejected_column_sum + $rejected_count;

                 $fatal_count=getCounts("Fatal","$transport_type","$date_id");
                 $fatal_column_sum=$fatal_column_sum + $fatal_count;

                 $failed_count=getCounts("Failed","$transport_type","$date_id");
                 $failed_column_sum=$failed_column_sum + $failed_count;

                 $total_row_sum=$archived_count + $archived_raw_count + $queued_count + $not_received_count + $rejected_count + $fatal_count + $failed_count;
                 $total_column_sum=$total_column_sum + $total_row_sum;

                 #$total_row_sum=commify($total_row_sum);
                 #$total_column_sum=commify($total_column_sum);

        #Set Default Background colors for HTML Table
        my $queued_bgcolor="white";
        my $failed_bgcolor="white";
        my $fatal_bgcolor="white";
        my $rejected_bgcolor="white";
        my $not_received_bgcolor="white";

        #Set Backgrond Colors depending on Processing State
        if ( $queued_count != 0 ) {$queued_bgcolor='green';}
        if ( $failed_count != 0 ) {$failed_bgcolor='red';}
        if ( $fatal_count != 0 ) {$fatal_bgcolor='red';}
        if ( $rejected_count != 0 ) {$rejected_bgcolor='red';}
        if ( $not_received_count != 0 ) {$not_received_bgcolor='orange';}

        #Print out each row of data in HTML to maile file
                print MAIL_FILE "<TR><TD align='center'>$ENVIRONMENT $transport_type</TD><TD align='center'>$date_id</TD><TD align='center'>$archived_count</TD><TD align='center'>$archived_raw_count</TD><TD align='center' bgcolor=\"$queued_bgcolor\">$queued_count</TD><TD align='center' bgcolor=\"$not_received_bgcolor\">$not_received_count</TD><TD align='center' bgcolor=\"$rejected_bgcolor\">$rejected_count</TD><TD align='center' bgcolor=\"$fatal_bgcolor\">$fatal_count</TD><TD align='center' bgcolor=\"$failed_bgcolor\">$failed_count</TD><TD align='center' bgcolor=\"$total_bgcolor\">$total_row_sum</TD></TR>\n";
                print "DEBUG: $date_id - $transport_type\n";
                #print "DEBUG: ARCHIVE|--|$archived_count|--|QUEUED|--|$queued_count|--|NOT_RECEIVED|--|$not_received_count|--|REJECTED|--|$rejected_count|--|FATAL|--|$fatal_count|--|FAILED|--|$failed_count|--|TOTAL|--|$total_row_sum\n";
              } #End If date_id

           } #End Foreach date_id

        #Print out row with Total Count of rows summed up
                print MAIL_FILE "<TR><TD align='center' bgcolor=\"$total_bgcolor\">-----------</TD><TD align='center' bgcolor=\"$total_bgcolor\">Total</TD><TD align='center' bgcolor=\"$total_bgcolor\">$archived_column_sum</TD><TD align='center' bgcolor=\"$total_bgcolor\">$archived_raw_column_sum</TD><TD align='center' bgcolor=\"$total_bgcolor\">$queued_column_sum</TD><TD align='center' bgcolor=\"$total_bgcolor\">$not_received_column_sum</TD><TD align='center' bgcolor=\"$total_bgcolor\">$rejected_column_sum</TD><TD align='center' bgcolor=\"$total_bgcolor\">$fatal_column_sum</TD><TD align='center' bgcolor=\"$total_bgcolor\">$failed_column_sum</TD><TD align='center' bgcolor=\"$total_bgcolor\">$total_column_sum</TD></TR>\n";


     print MAIL_FILE "</TABLE>";
     print MAIL_FILE "<br><br>\n";
     close MAIL_FILE;
  }

####################################################################################################################################

sub prepareEmail {

   #Prepares the first part of an HTML email

    open MAIL_FILE, ">", "$mail_file" or die $!;
    print MAIL_FILE "From: SRE Alert Monitoring <no-reply\@company.com>\n";
    print MAIL_FILE "To: $TO_EMAIL_ADDRESSES\n";
    print MAIL_FILE "Subject: Daily Reconcilation Report (V1) - $ENVIRONMENT\n";
    print MAIL_FILE "Mime-Version: 1.0\n";
    print MAIL_FILE "Content-Type: text/html\n";
    print MAIL_FILE "Content-Disposition: inline\n";
    print MAIL_FILE  "Content-Transfer-Encoding: 7bit\n";

    print MAIL_FILE  "<br>\n";
    print MAIL_FILE  "Report Generated on $TODAY (PST)<br>\n";
    print MAIL_FILE  "<br><br><br>\n";

    print MAIL_FILE "<HTML>\n";
    print MAIL_FILE "<BODY>\n";
    close MAIL_FILE;

}


####################################################################################################################################

sub sendEmail {

#Finalizes the HTML email and sends it
  open MAIL_FILE, ">>", "$mail_file" or die $!;
  print MAIL_FILE "</BODY>\n";
  print MAIL_FILE "</HTML>\n";
  print MAIL_FILE "<br>\n";
  print MAIL_FILE "<br>\n";
  close MAIL_FILE;


 #Finally send the MAIL_FILE Out
  open MAIL_FILE, "<", "$mail_file" or die $!;
  my $sendmail = "/usr/sbin/sendmail -t";
  open(SENDMAIL, "|$sendmail") or die "Cannot open $sendmail: $!";
  print SENDMAIL <MAIL_FILE>;
  close MAIL_FILE;
  close(SENDMAIL);


}

######### MAIN ###############
prepareEmail();
getDatesToProcess("SMTP");
processReport("SMTP");
getDatesToProcess("HTTP");
processReport("HTTP");
sendEmail();

$dbhMetricsDB->disconnect();
ASingh@fab-jpus01-warden-h5:/opt/company/RECON_TOOLS/MASTER_SCRIPTS$
