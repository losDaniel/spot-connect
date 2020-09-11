"""
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot-connect

Toolbox for working with AWS - bash_scripts.py: 

The bash_scripts sub-module contains functions that return pre-set bash scripts 
that can be used for conventional tasks such as complex package installations 
for common packages, updating github repos, and managing spot-fleet settings. 
    
MIT License 2020
"""

import base64


def init_userdata_script(python3=True):
    '''Initialize a script to use with for the linux instance user_data.     
    For more information on submitting user_data to EC2 instance visit https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html.     
    The cloud-init output log file (/var/log/cloud-init-output.log) captures console output so it is easy to debug your scripts following a launch if the instance does not behave the way you intended.
    '''
    script = '#!/bin/bash\n'
    return script 


def script_to_userdata(script):
    '''Takes a script as a string argument and converts it to a base64 encoded string that can be submitted as user_data to ec2 instances'''
    return base64.b64encode(bytes(str(script), 'utf-8')).decode('ascii')


def run_command_as_user(command:str, user:str, delimiter:str):
    '''Runs the given command as the "user" on a linux command line'''
    return 'sudo runuser -l '+user+" -c '"+command+"'"+delimiter


def compose_s3_sync_script(source, dest, instance_path, logfile='s3_sync_log', delimiter='\n', script=''):
    '''Syncs an instance and s3 and then shuts down the instance.'''
    
    # Run the aws s3 sync command in the background and send the output to download_<didx>.txt
    script +='nohup aws s3 sync '+source+' '+dest+' &> '+instance_path+'/'+logfile+'.txt &'+delimiter
    # Get the job id for the last command
    script +='curpid=$!'+delimiter
    # When the job with the given job id finishes, shut down and terminate the instance
    script +="nohup sh -c 'while ps -p $0 &> /dev/null; do sleep 10 ; done && sudo shutdown -h now ' $curpid &> s3_transfer.txt &"+delimiter  
    
    return script
    

def update_git_repo(repo_path, branch=None, repo_link=None, delimiter='\n', script=''):
    '''Update the github repo at the given path. Use the repo_link arg for private repos that require authentication details'''
    
    script +='cd '+repo_path+delimiter
    if branch is not None: 
        script +='git checkout '+branch+delimiter
    if repo_link is None:
        script += 'git pull origin'
    else:
        script+='git pull '+repo_link+delimiter
        
    return script


def install_ta_lib(download=False, install_as_user=None, delimiter='\n', script=''):
    '''Download (optional) and install ta-lib. The ta-lib folder must be in the wd'''
    if download: 
        script += 'wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz'+delimiter
        script += 'tar -xzf ta-lib-0.4.0-src.tar.gz'+delimiter
        
    # Install ta-lib
    script+= 'cd ta-lib/'+delimiter
    script+= 'sudo ./configure'+delimiter
    script+= 'sudo make'+delimiter
    script+= 'sudo make install'+delimiter
    if install_as_user is None: 
        script+= 'pip install ta-lib'+delimiter
    else: 
        script+= 'sudo runuser -l '+install_as_user+" -c 'pip install ta-lib'"+delimiter

    # Return to the working directory 
    script+= 'cd ..'+delimiter
    script+= 'echo "Installed ta-lib"'+delimiter
    script+= '\n'

    return script 


def compose_mount_script(filesystem_dns, base='/home/ec2-user', delimiter='\n', script=''):
    '''Create a script of linux commands that can be run on an instance to connect an EFS'''
    
    script+='mkdir '+base+'/efs'+delimiter
    script+='sudo mount -t nfs -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport '+filesystem_dns+':/   '+base+'/efs '+delimiter
    script+='cd '+base+'/efs'+delimiter
    # go-rwx removes read, write, execute permissions from the group and other users. It will not change permissions for the user that owns the file.
    script+='sudo chmod go+rw .'+delimiter
    script+='echo EFS Mounted'+delimiter
    script+='\n'
                    
    return script 


def shutdown_instance_after_command(command:str, command_log='', run_as_user='', delimiter='\n', script=''):
    '''
    Run a command and shut down the instance after the command has completed running (use this to run a python script, for example).
    This method is inteneded for use in scripts submitted as <user_data> to instances (i.e. run as root at the start of each script). 
    To check the output of the user_data script, log onto the instance and view the "/var/log/cloud-init-output.log" file. 
    __________
    parameters
    - command : str. The command you want to run on the instance. 
    - command_log : str. Path and/or name of a .txt file that will store the command output on the instance. 
    - run_as_user : str. If submitted, the command will be run as this user on the instance. 
    - delimited : str. Default delimiter on the script. 
    - script : str. Script as string. 
    '''
                      
    if command_log != '': 
        logname = '> '+command_log
    else: 
        logname = '' 

    if run_as_user=='': 
        script += command+logname+delimiter
    else: 
        script += run_command_as_user(command, run_as_user, '')+logname+delimiter
    
    # Wait until the previous job is done and then shutdown the instance 
    script+= "nohup sh -c 'while ps -p $0 &> /dev/null; do sleep 10 ; done && sudo shutdown -h now ' $curpid &> run.txt &"

    return script    


def cancel_fleet_after_command(command:str, region:str, command_log='', run_as_user='', delimiter='\n', script=''):
    '''
    Run a command and then cancel the spot fleet request that requested the current instance. The instance is terminated as a result of this cancelation request as well.
    This method is inteneded for use in scripts submitted as <user_data> to instances (i.e. run as root at the start of each script). 
    To check the output of the user_data script, log onto the instance and view the "/var/log/cloud-init-output.log" file. 
    __________
    parameters
    - command : str. The command you want to run on the instance. 
    - command_log : str. Path and/or name of a .txt file that will store the command output on the instance. 
    - run_as_user : str. If submitted, the command will be run as this user on the instance. 
    - delimited : str. Default delimiter on the script. 
    - script : str. Script as string. 
    '''
        
    if command_log != '': 
        logname = '> '+command_log
    else: 
        logname = '' 

    script += 'INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)'+delimiter
    
    script += 'AWS_REGION="'+region+'"'+delimiter
    script += 'SPOT_FLEET_REQUEST_ID=$(aws ec2 describe-spot-instance-requests --region $AWS_REGION --filter "Name=instance-id,Values='+"'$INSTANCE_ID'"+'" --query "SpotInstanceRequests[].Tags[?Key=='+"'aws:ec2spot:fleet-request-id'"+'].Value[]" --output text)'+delimiter
    
    if run_as_user=='': 
        script += command+logname+delimiter
    else: 
        script += run_command_as_user(command, run_as_user, '')+logname+delimiter
       
    script += 'mkdir dontgivenofucks'+delimiter
         
    script += 'aws ec2 cancel-spot-fleet-requests --region $AWS_REGION --spot-fleet-request-ids $SPOT_FLEET_REQUEST_ID --terminate-instances'
    
    return script 


