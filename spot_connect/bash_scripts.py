"""
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot-connect

Toolbox for working with AWS - bash_scripts.py: 

The bash_scripts sub-module contains functions that return pre-set bash scripts 
that can be used for conventional tasks such as complex package installations 
for common packages, updating github repos, and managing spot-fleet settings. 
    
MIT License 2020
"""


def compose_s3_sync_script(source, dest, instance_path, logfile='s3_sync_log', command=''):
    '''This script syncs an instance and s3 and then shuts down the instance.'''
    
    # Run the aws s3 sync command in the background and send the output to download_<didx>.txt
    command +='nohup aws s3 sync '+source+' '+dest+' &> '+instance_path+'/'+logfile+'.txt &\n'
    # Get the job id for the last command
    command +='curpid=$!\n'
    # When the job with the given job id finishes, shut down and terminate the instance
    command +="nohup sh -c 'while ps -p $0 &> /dev/null; do sleep 10 ; done && sudo shutdown -h now ' $curpid &> s3_transfer.txt &\n"
    
    return command
    

def update_git_repo(repo_path, branch=None, repo_link=None, command=''):
    '''Update the github repo at the given path. Use the repo_link arg for private repos that require authentication details'''

    command +='cd '+repo_path+'\n'
    if branch is not None: 
        command +='git checkout '+branch+'\n'
    if repo_link is None:
        command += 'git pull origin'
    else:
        command+='git pull '+repo_link+'\n'

    return command


def install_ta_lib(download=False, command=''):
    '''Download (optional) and install ta-lib. The ta-lib folder must be in the wd'''
    if download: 
        command += 'wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz\n'
        command += 'tar -xzf ta-lib-0.4.0-src.tar.gz\n'
    # Install ta-lib
    command+= 'cd ta-lib/\n'
    command+= 'sudo ./configure\n'
    command+= 'sudo make\n'
    command+= 'sudo make install\n'
    command+= 'pip install ta-lib\n'
    # Return to the working directory 
    command+= 'cd ..\n'    

    return command 


def run_file_then_shutdown(py_filepath, 
                           args='', 
                           logname='',
                           command=''):
    '''
    Execute a python script and shut down the instance when its done. Run the job in such a way that it continues to run even if the user logs in and out of the instance.
    __________
    parameters
    - py_filepath : str. Filepath ending in .py that you want to execute 
    - args : str. arguments for the file. 
    - logname : str. filepath to a log file where the output of the python file can be stored. 
    - command : existing script to add to.     
    '''
                      
    if logname != '': 
        logname = '> '+logname+' &'
                                       # In the project folder we want to run the script that will execute the apr recognition 
    command+= 'nohup python '+py_filepath+' '+args+' &'+logname+'\n'
    command+= 'curpid=$!\n'
    
    # Wait until the previous job is done and then shutdown the instance 
    command+= "nohup sh -c 'while ps -p $0 &> /dev/null; do sleep 10 ; done && sudo shutdown -h now ' $curpid &> run.txt &\n"

    return command    


def run_file_then_reduce_fleet(spot_fleet_req_id, py_filepath, args='', logname='', region='us-east-2', command=''):
    '''Runs a python script and then reduces spot fleet capacity and terminates itself. If fleet capacity is 1, cancels fleet request'''

    if logname != '': 
        logname = '> '+logname+' &'

    command += 'INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)'
    command += 'INSTANCE_AZ=$(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone)'
    command += 'AWS_REGION="'+region+'"'    

    command += 'if [ $INSTANCE_ID ]; then'
    command += 'python '+py_filepath+' '+args+' '+logname+'\n'
    command += 'fi' 
                                                                                                               # Needed to include the right " and ' characters here 
    command += 'SPOT_FLEET_REQUEST_ID="'+spot_fleet_req_id+'"\n'
    command += 'SPOT_FLEET_CAPACITY=$(aws ec2 describe-spot-fleet-requests --spot-fleet-request-ids $SPOT_FLEET_REQUEST_ID --region $AWS_REGION --query "SpotFleetRequestConfigs[0].SpotFleetRequestConfig.TargetCapacity")\n'

    # If the spot fleet capacity is greater than 1 then reduce the capacity by 1, wait a moment, then terminate the instance.  
    command += 'if [ $SPOT_FLEET_CAPACITY -gt 1 ]; then\n'    
    command += '    MODIFIED_CAPACITY=$((SPOT_FLEET_CAPACITY - 1))\n'    
    command += '    aws ec2 modify-spot-fleet-request --target-capacity $MODIFIED_CAPACITY --spot-fleet-request-id $SPOT_FLEET_REQUEST_ID --region $AWS_REGION\n'    
    command += '    sleep 5\n'
    command += '    sudo shutdown -h now'
    
    command += 'elif [ $SPOT_FLEET_CAPACITY = 1 ]; then\n'    
    command += '    aws ec2 cancel-spot-fleet-requests --region $AWS_REGION --spot-fleet-request-ids $SPOT_FLEET_REQUEST_ID --terminate-instances\n'
    command += 'fi\n'
    
    return command 






#
#    

# If spot fleet capacity is greater than 1: 
    # reduce the capacity by 1 
    
    # modify spot fleet fleet to new capacity 
    
# If spot fleet capacity is 1: 
    # cancel spot fleet request 


#
#
#
#  modify-spot-fleet-request
#[--excess-capacity-termination-policy <value>]
#--spot-fleet-request-id <value>
#[--target-capacity <value>]
#[--on-demand-target-capacity <value>]
#[--cli-input-json <value>]
#[--generate-cli-skeleton <value>]
