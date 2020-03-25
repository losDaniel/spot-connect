"""
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot-connect

Toolbox for launching an AWS spot instance: 

This package consists mainly of the boto3 functions that are used to request, 
launch and interact with a spot instance. These functions are used in the 
spot_connect.py script which can be launched from the command line or the 
spotted class which can be run from a notebook or python script

MIT License 2020
"""

import sys, os, boto3 
from spot_connect import spot_instances, spot_utils, interactive

def run_script(instance, user_name, script, cmd=False, port=22, kp_dir=os.getcwd()):
    '''
    Run a script on the the given instance 
    __________
    parameters
    - instance : dict. Response dictionary from ec2 instance describe_instances method 
    - user_name : string. SSH username for accessing instance, default usernames for AWS images can be found at https://alestic.com/2014/01/ec2-ssh-username/
    - script : string. ".sh" file or linux/unix command (or other os resource) to execute on the instance command line 
    - cmd : if True, script string is treated as an individual argument 
    - port : port to use to connect to the instance 
    '''
    
    if cmd: 
        commands = script
    else:   
        commands = open(script, 'r').read().replace('\r', '')
        
    client = spot_instances.connect_to_instance(instance['PublicIpAddress'],kp_dir+'/'+instance['KeyName'],username=user_name,port=port)
    
    session = client.get_transport().open_session()
    session.set_combine_stderr(True)                                           # Combine the error message and output message channels

    session.exec_command(commands)                                             # Execute a command or .sh script (unix or linux console)
    stdout = session.makefile()                                                # Collect the output 
    
    try:
        for line in stdout:
            print(line.rstrip(), flush=True)                                   # Show the output 
    
    except (KeyboardInterrupt, SystemExit):
        print(sys.stderr, 'Ctrl-C, stopping', flush=True)                      # Keyboard interrupt 
    client.close()                                                             # Close the connection    
    
    return True


def active_shell(instance, user_name, port=22, kp_dir=os.getcwd()): 
    '''
    Leave a shell active
    __________
    parameters 
    - instance : dict. Response dictionary from ec2 instance describe_instances method 
    - user_name : string. SSH username for accessing instance, default usernames for AWS images can be found at https://alestic.com/2014/01/ec2-ssh-username/
    - port : port to use to connect to the instance 
    '''    
    
    client = spot_instances.connect_to_instance(instance['PublicIpAddress'],kp_dir+'/'+instance['KeyName'],username=user_name,port=port)

    console = client.invoke_shell()                                            
    console.keep_this = client                                                

    session = console.get_transport().open_session()
    session.get_pty()
    session.invoke_shell()

    try:
        interactive.interactive_shell(session)

    except: 
        print('Logged out of interactive session.')

    session.close() 
    return True 


def upload_to_ec2(instance, user_name, files, remote_dir='.', kp_dir=os.getcwd()):
    '''
    Upload files directly to an EC2 instance. Speed depends on internet connection and not instance type. 
    __________
    parameters 
    - instance : dict. Response dictionary from ec2 instance describe_instances method 
    - user_name : string. SSH username for accessing instance, default usernames for AWS images can be found at https://alestic.com/2014/01/ec2-ssh-username/
    - files : string or list of strings. single file, list of files or directory to upload. If it is a directory end in "/" 
    - remote_dir : '.'  string.The directory on the instance where the files will be uploaded to 
    '''
    client = spot_instances.connect_to_instance(instance['PublicIpAddress'],kp_dir+'/'+instance['KeyName'],username='ec2-user',port=22)
    print('Connected. Uploading files...')
    stfp = client.open_sftp()

    try: 
    	for f in files: 
            print('Uploading %s' % str(f.split('\\')[-1]))
            stfp.put(f, remote_dir+'/'+f.split('\\')[-1], callback=spot_utils.printTotals, confirm=True)

    except Exception as e:
        raise e

    print('Uploaded to %s' % remote_dir)
    return True 


def download_from_ec2(instance, username, get, put='.'):
    '''
    Download files directly from an EC2 instance. Speed depends on internet connection and not instance type. 
    __________
    parameters 
    - instance : dict. Response dictionary from ec2 instance describe_instance method 
    - user_name : string. SSH username for accessing instance, default usernames for AWS images can be found at https://alestic.com/2014/01/ec2-ssh-username/
    - get : str or list of str. File or list of file paths to get from the instance 
    - put : str or list of str. Folder to place the files in `get` 
    '''
    client = boto3.client('ec2', region_name='us-west-2')
    client = spot_instances.connect_to_instance(instance['PublicIpAddress'],instance['KeyName'],username=username,port=22)

    stfp = client.open_sftp()

    for idx, file in enumerate(get): 
        try: 
            stfp.get(file,put[idx], callback=spot_utils.printTotals)
        except Exception as e: 
            print(file)
            raise e
    return True 


def terminate_instance(instance_id):
    '''Terminate  an instance using the instance ID'''
    
    if type(instance_id) is str: 
        instances = [instance_id]

    elif type(instance_id) is list: 
        instances = instance_id

    else: 
        raise Exception('instance_id arg must be str or list')

    ec2 = boto3.resource('ec2')
    ec2.instances.filter(InstanceIds=instances).terminate()
