root@fab-jpdr01-sftp-h1:~# cat /data/JPMC_SFTP/prodnam/import_participants.sh
#!/bin/bash


#Changed /parent_directory_path to file_source_path to better reflect what the directory is
#Created post_processing_directory to put files in after they have been processed to make troubleshooting easier
#Changed fully qualified props_file in if loop that includes it if that file is present
#Changed import_partcipants function to take 3 parameters instead of 2 / Change call to function to include 3 parameters
#Added log file purging based on retention_period - logs now have dates appended

props_file="/data/JPMC_SFTP/prodnam/import_participants.properties"
processed_files_count=0
import_success_flag=0
file_format=""
file_source_path=""
post_processing_directory=""

decrypted_password=""

check_properties_file(){
        if [ -f $props_file ];
        then
                . ${props_file}
                echo -e "\n\n---------------------------------------------------------------------------------------------------" >> $log_file
                echo -e "\n[INFO] Loading the properties file: ${props_file}..." >> $log_file
        else
                echo -e "\n\n\n---------------------------------------------------------------------------------------------------" >> "/tmp/import_participants.log"
                echo -e "\n[ERROR] properties file missing..." >> "/tmp/import_participants.log"
                exit
        fi
}


log_info(){
        echo -e "\n[INFO] TENANT NAME : $tenant_name  \n[INFO] DATE        : `date` " >> $log_file
}

create_dirs_if_not_present(){
        mkdir -p $file_source_path
        mkdir -p $post_processing_directory/$processed_files_folder
        mkdir -p $post_processing_directory/$failed_files_folder
        mkdir -p $log_file_dir
}

decrypt_password(){

        #the password field in properties file is an encrypted one
        encryptedPassword=$password
        aesDecryptedPassword=`echo $encryptedPassword | openssl enc -aes-128-cbc -d -a -salt -pass pass:$publicKey`
        decryptedPassword=`echo $aesDecryptedPassword | base64 --decode`
}

post_participant(){

        import_success_flag=0
        echo "[INFO] POST RESULT : " >> $log_file

        #construct the url based on the current  file which is being passed as param to this function (i.e). $1
        post_api_url=$post_api_url_part1$1$post_api_url_part2$file_format
        echo -e "[INFO] URL : $post_api_url" >> $log_file

        echo -e "[INFO] cURL Response :         " >> $log_file
        curl_result=$(curl -X POST --tlsv1.2 --digest -u "$user_name:$decryptedPassword" $post_api_url --insecure --data-binary @$file_source_path/$1) >> $log_file
        echo $curl_result >> $log_file

        #updating the flag so that the  file will be moved to the processed folder only if the POST request is successful
        import_success_flag=$(echo $curl_result | grep -b -c "Import success")

        echo -e "[INFO] post request completed..." >> $log_file

}

purge_old_files(){

        find $post_processing_directory/$processed_files_folder -type f -mtime +$retention_period -exec rm -f {} \;
        echo -e "[INFO] Processed files older than the retention period are deleted..." >> $log_file

        find $log_file_dir -type f -mtime +$retention_period -exec rm -f {} \;
        echo -e "[INFO] Log files older than the retention period are deleted..." >> $log_file
}

import_participants(){

        file_format=$1
        file_source_path=$2
        post_processing_directory=$3

        #create sub directories
        create_dirs_if_not_present

        #Get the total number of files that are of the type
        number_of_files=`cd $file_source_path && ls *.$1 | wc -l`
        echo -e "\n\n[INFO] Number of $file_format files : $number_of_files" >> $log_file

        if [ $number_of_files -eq 0 ]; then
                        echo -e "\n[INFO] No new $file_format files to import" >> $log_file
        fi

        for ((i=1; i<=$number_of_files; i+=1)); do

                #During each iteraration, get the oldest  fil
                oldest_file=`cd $file_source_path && ls *$1 -rt|head -n1`

                echo -e "[INFO] $file_format FILE  : $oldest_file" >> $log_file

                #perform post request for that  file
                post_participant $oldest_file

                if [ $import_success_flag -eq 1 ];
                then
                        echo -e "[INFO] $oldest_file is successfully imported\n" >> $log_file
                        #then, that  file is being moved to the processed folder
                        mv $file_source_path/$oldest_file $post_processing_directory/$processed_files_folder

                #retry the POST request for specified number of times
                else
                        for((j=1; j<=$number_of_retries; j+=1)); do
                                if [ $import_success_flag -eq 0 ];
                                then
                                        echo -e "\n[INFO] Retrying the POST request - RETRY Count : $j " >> $log_file
                                        post_participant $oldest_file
                                fi
                        done
                fi

                if [ $import_success_flag -eq 0 ];
                then
                        mv $file_source_path/$oldest_file $post_processing_directory/$failed_files_folder
                        echo -e "\n>>>> [ERROR] $oldest_file import failed. File moved to the failed files directory <<<<" >> $log_file
                fi

                processed_files_count=$i
        done

        echo -e "\n[INFO] Import completed... Total $file_format files processed : $processed_files_count" >> $log_file

        #now delete the  files older than the retention period mentioned in properties file
        purge_old_files

}

#check if the properties files exists
check_properties_file

#Log basic info
log_info

#decrypt the endpoint password for performing post request
decrypt_password

#the generic function is called separately for different file formats. parameter : (1) file extension (2) parent directory path
import_participants "ldif" $ldif_file_path $ldif_post_processing_dir
import_participants "csv" $csv_file_path $csv_post_processing_dir
