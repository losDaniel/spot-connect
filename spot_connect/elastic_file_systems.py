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

import boto3
from netaddr import IPNetwork

import sys, time

def launch_efs(system_name, region='us-west-2', launch_wait=3):
    '''Create or connect to an existing file system'''

    client = boto3.client('efs', region_name=region)
    
    file_systems = client.describe_file_systems(CreationToken=system_name)['FileSystems']                    

    # If there are no file systems with the `system_name` 
    if len(file_systems)==0:                                                   

        sys.stdout.write('Creating EFS file system...')
        sys.stdout.flush()  
        
        # Create the file system 
        client.create_file_system(                                             
            CreationToken=system_name,
            PerformanceMode='generalPurpose',
        )

        initiated=False 

        sys.stdout.write('Initializing...')
        sys.stdout.flush()  

        # Wait until the file system is detectable 
        while not initiated: 
            
            try: 
                file_system = client.describe_file_systems(CreationToken=system_name)['FileSystems'][0]
                initiated=True
            
            except: 
                sys.stdout.write(".")
                sys.stdout.flush() 
                time.sleep(launch_wait)

        print('Detected')

    else: 
        print('...EFS file system already exists')
        file_system = file_systems[0]                                          # If the file system exists 
                
    available=False
    sys.stdout.write('Waiting for availability...')
    sys.stdout.flush() 

    while not available: 

        file_system = client.describe_file_systems(CreationToken=system_name)['FileSystems'][0]

        if file_system['LifeCycleState']=='available':
            available=True
            print('...Available')
            
        else: 
            sys.stdout.write(".")
            sys.stdout.flush() 
            time.sleep(launch_wait)
        
    return file_system 


def retrieve_efs_mount(file_system_name, instance, new_mount=False, region='us-west-2', mount_wait=3): 
    
    # Launch or connect to an EFS 
    file_system = launch_efs(file_system_name, region=region)                  
    file_system_id = file_system['FileSystemId']
        
    # Connect and check for existing mount targets on the EFS 
    client = boto3.client('efs', region_name=region)                            
    mount_targets = client.describe_mount_targets(FileSystemId=file_system_id)['MountTargets']

    # If no mount targets are detected
    if (len(mount_targets)==0):   
        new_mount = True 

    # Setup a new mount on the file system 
    if new_mount:                                               

        sys.stdout.write('No mount target detected. Creating mount target...')
        sys.stdout.flush() 

        subnet_id = instance['SubnetId']                                       # Gather the instance subnet ID. Subnets are your personal cloud, for a full explanation see https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Subnets.html
        security_group_id = instance['SecurityGroups'][0]['GroupId']           # Get the instance's security group
        
        ec2 = boto3.resource('ec2')                                            
        subnet = ec2.Subnet(subnet_id)                                         # Get the features of the subnet
        
        net = IPNetwork(subnet.cidr_block)                                     # Get the IPv4 CIDR block assigned to the subnet.
        ips = [str(x) for x in list(net[4:-1])]                                # The CIDR block is a block or range of IP addresses, we only need to assign one of these to a single mount

        ipid = 0 
        complete = False 

        while not complete: 
            try: 
                response = client.create_mount_target(                         # Create the mount target 
                    FileSystemId=file_system_id,                               # Under the file system just created 
                    SubnetId=subnet_id,                                        # Under the same subnet as the EC2 instance you've just created 
                    IpAddress=ips[ipid],                                       # Assign it the first IP Adress from the CIDR block assigned to the subnet 
                    SecurityGroups=[
                        security_group_id,                                     # Apply the security group which must have ingress rules to allow NFS client connections (enable port 2049)
                    ]
                )
                complete=True
            except Exception as e: 
                if 'IpAddressInUse' in str(e):
                    ipid+=1 
                else: 
                    raise(e) 

        initiated = False

        sys.stdout.write('Initializing...')
        sys.stdout.flush() 

        # Probe for the mount target until it is detectable 
        while not initiated: 
            try:                                                               
                mount_target = client.describe_mount_targets(MountTargetId=response['MountTargetId'])['MountTargets'][0]
                initiated = True 
            except: 
                sys.stdout.write(".")
                sys.stdout.flush() 
                time.sleep(mount_wait)

        sys.stdout.write('Detected')
        sys.stdout.flush() 

    else: 
        mount_target = mount_targets[0]
    
    instance_dns = instance['PublicDnsName']
    filesystem_dns = file_system_id+'.efs.'+region+'.amazonaws.com'
            
    return mount_target, instance_dns, filesystem_dns


def compose_mount_script(filesystem_dns):
    '''Create a script of linux commands that can be run on an instance to connect an EFS'''
    
    script = ''
    script+='mkdir ~/efs &> /dev/null'+'\n'
    script+='sudo mount -t nfs -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport '+filesystem_dns+':/   ~/efs '+'\n'
    script+='cd ~/efs'+'\n'
    script+='sudo chmod go+rw .'+'\n'
    script+='mkdir ~/efs/data &> /dev/null'+'\n'
                    
    return script 

