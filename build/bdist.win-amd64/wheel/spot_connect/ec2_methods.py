"""
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot-connect

Toolbox for launching an AWS spot instance - ec2_methods.py:
    
The ec2_methods sub-module contains functions for launching or connecting to 
spot instances or making and manging spot-fleet requests. 

MIT License 2020
"""

import boto3, paramiko, time, sys, os
from path import Path

root = Path(os.path.dirname(os.path.abspath(__file__)))

from spot_connect import iam_methods

def get_spot_instance(spotid,
                      profile, 
                      instance_profile='', 
                      monitoring=True, 
                      spot_wait_sleep=5, 
                      instance_wait_sleep=5, 
                      kp_dir=None, 
                      enable_nfs=True, 
                      enable_ds=True,
                      using_instance_id=False):
    '''
    Launch a spot instance or connect to an existing one using the preconfigured aws account on boto3. Returns instance ID and profile (if the returned profile has the "key_pair" and "security_group" params filled out if they were empty) 
    __________
    parameters 
    - spotid : name for the spot instance's launch group. Try and keep launch groups unique to active instances.  
    - profile : dictionary with key parameters 
        > image_id : image ID from AWS. go to the launch-wizard to get the image IDs or use the boto3 client.describe_images() with Owners of Filters parameters to reduce wait time and find what you need.
        > instance_type : get a list of instance types and prices at https://aws.amazon.com/ec2/spot/pricing/ 
        > price : the maximum price to bid for a spot instance: get a list of prices at https://aws.amazon.com/ec2/spot/pricing/ 
        > region : the region to access
    - instance_profile : str. allows the user to submit an instance profile with attached IAM role specifications 
    - spot_wait_sleep : how much time to wait between each probe of whether the spot request has been placed 
    - instance_wait_sleep : how much time to wait between each probe of whether the spot request has been filled
    - key_pair_dir : string. directory to store the private key files
    - enable_nfs : bool, default True. When true, add NFS ingress rules to security group (TCP access from port 2049)
    - enable_ds : bool, default True. When true, add HTTP ingress rules to security group (TCP access from port 80)
    - instance_id : bool, default False. if True, spotid will be treated as the instance ID instead of the launch-group
    '''

    print('Profile:')
    print(profile)
    print('')    

    # Connect to aws ec2 subnet as a client 
    client = boto3.client('ec2', region_name=profile['region'])                
    
    #~#~#~#~#~#~#~#~#~#~#
    #~#~# Key Pairs #~#~#
    #~#~#~#~#~#~#~#~#~#~#
    
    if not using_instance_id:
        # If no key_par exists for the current spot instance id
        if 'key_pair' not in profile:                                               
            # Log a keypair in the profile dictionary 
            profile['key_pair']=('KP-'+spotid,'KP-'+spotid+'.pem')                 
    
        try: 
            iam_methods.create_key_pair(client, profile, kp_dir)
        except Exception as e: 
            if 'InvalidKeyPair.Duplicate' in str(e): 
                print('Key pair detected, re-using...')
            else: 
                sys.stdout.write("Was not able to find Key-Pair in default directory "+str(kp_dir))
                sys.stdout.write("\nTo reset default directory run: spot_connect.sutils.set_default_kp_dir(<dir>)")
                sys.stdout.flush()   
                raise e 

    #~#~#~#~#~#~#~#~#~#~#~#~#~#
    #~#~# Security Groups #~#~#
    #~#~#~#~#~#~#~#~#~#~#~#~#~#

    if not using_instance_id:
        # If no security group was submitted 
        if 'security_group' not in profile:                                                    
            # Create and retrieve the security group 
            sg = iam_methods.get_security_group(client, 'SG-'+spotid, enable_nfs=enable_nfs, enable_ds=enable_ds, firewall_ingress_settings=profile['firewall_ingress'])    
    
            # For the profile we need a tuple of the security group ID and the security group name. 
            profile['security_group'] = (sg['GroupId'],'SG-'+spotid)               # Add the security group ID and name to the profile dictionary 

    #~#~#~#~#~#~#~#~#~#~#~#~#~#~#
    #~#~# Instance Requests #~#~#
    #~#~#~#~#~#~#~#~#~#~#~#~#~#~#

    # TODO : add the option to identify spot instances by id. 
    # TODO : organize the security-group, launch-group naming so that everything maps to AWS.  
    
    # If the user is using the instance ID then filter using instance id 
    if using_instance_id:
        reservations = client.describe_instances(Filters=[{'Name':'instance-id', 'Values':[spotid]},
                                                      {'Name':'instance-state-name','Values':['pending','running']}])['Reservations']
        if len(reservations)==0: 
            raise Exception('Unable to find instance with given id. Cannot create instances based on instance-ids. Submit a name to create an instance. Exiting.')
        instance_id = spotid
            
    # Otherwise, filter using the instance's launch group 
    else:     
        spot_requests = client.describe_spot_instance_requests(Filters=[{'Name':'launch-group', 'Values':[spotid]},
                                                                         {'Name':'state','Values':['open','active']}])['SpotInstanceRequests']
        
        # If there are open/active instance requests with the same name (should only be one) re-use the first one that was found 
        if len(spot_requests)>0:               
            print('Spot instance found')                                    
            spot_req_id = spot_requests[0]['SpotInstanceRequestId']                
        else:
            # Otherwise request a new one 
            print('Requesting spot instance')
    
            launch_specs = {
                    'SecurityGroupIds': [
                        profile['security_group'][0],
                    ],
                    'SecurityGroups': [
                        profile['security_group'][1],
                    ],
                    'EbsOptimized': False,                                         # do not optimize for EBS storage 
                    'ImageId': profile['image_id'],                                # AWS image ID. List available programatically or through launch wizard 
                    'InstanceType': profile['instance_type'],                      # Instance type. List available programatically or through wizard or at https://aws.amazon.com/ec2/spot/pricing/ 
                    'KeyName': profile['key_pair'][0],                             # Name for the key pair
                    'Monitoring' : {'Enabled': monitoring},                        # Enable monitoring
            }
            if instance_profile!='':
                launch_specs['IamInstanceProfile']= {                              # Define the IAM role for your instance 
                             'Name': instance_profile,                                       
                }
    
            response = client.request_spot_instances(                              
                AvailabilityZoneGroup=profile['region'],
                ClientToken=spotid,                                                # submit a name to ensure idempotency 
                DryRun=False,                                                      # if True, checks if you have permission without actually submitting request
                InstanceCount=1,                                                   # number of individual instances 
                LaunchGroup=spotid,
                LaunchSpecification=launch_specs,
                SpotPrice=profile['price'],                                        # Must be greater than current instance type price for region, available at https://aws.amazon.com/ec2/spot/pricing/ 
                Type='one-time',                                                   # Persisitence is usually not necessary (given storage backup) or advisable with spot instances 
                InstanceInterruptionBehavior='terminate',                          # Instance terminates if typing `shutdown -h now` in the console
            )
            spot_req_id = response['SpotInstanceRequests'][0]['SpotInstanceRequestId']

        # Check if the instance id has been created (will only delay if the instance was just created)
        attempt = 0 
        instance_id = None
        spot_tag_added = False
        
        # Wait for the instance to initialize, retrieve the request by ID 
        while not instance_id:  # I know this is unusual cause its not a boolean but it works.                                                     
            spot_req = client.describe_spot_instance_requests(Filters=[{'Name':'spot-instance-request-id', 'Values':[spot_req_id]}])['SpotInstanceRequests']
    
            if len(spot_req)>0:          
    
                spot_req = spot_req[0]                                             
    
                # If no tag has been added yet add a tag to the request with the spot instance name 
                if not spot_tag_added:     
                    client.create_tags(Resources=[spot_req['SpotInstanceRequestId']], Tags=[{'Key':'Name','Value':spotid}])
                    spot_tag_added=True
                
                # If the request failed raise an exception 
                if spot_req['State']=='failed':                                    
                    raise Exception('Spot Request Failed')
    
                # If an instance ID was returned with the spot request we exit the while loop 
                if 'InstanceId' in spot_req:                                       
                    instance_id = spot_req['InstanceId']
    
                # Otherwise we continue to wait 
                else:                                                              
                    sys.stdout.write(".")
                    sys.stdout.flush()                                                   
                    time.sleep(spot_wait_sleep)
            else:             
                # If its the first attempt print launching and follow that with a bunch of periods until we're done
                if attempt==0:
                    sys.stdout.write('Launching...')
                    sys.stdout.flush()             
                
                # If a new spot request was submitted it may take a moment to register
                sys.stdout.write(".")
                sys.stdout.flush()                                                 
                
                # Wait and attempt to connect again 
                time.sleep(spot_wait_sleep)                                        
    
                attempt+=1 

    print('Retrieving instance by id')

    try: 
        reservations = client.describe_instances(Filters=[{'Name':'instance-id', 'Values':[instance_id]}])['Reservations']
        instance = reservations[0]['Instances'][0]                             

    except Exception as e: 
        raise e 
        
    sys.stdout.write('Got instance: '+str(instance['InstanceId'])+'['+str(instance['State']['Name'])+']')
    sys.stdout.flush() 
    
    if str(instance['State']['Name'])=='terminated':
        raise Exception('Desired spot request has been terminated, please choose a new instance name or wait until the terminated spot request has expired in the AWS console')

    instance_status = check_instance_initialization(instance_id, client=client, instance_wait_sleep=instance_wait_sleep)

    if instance_status!='ok':                                                  # Wait until the instance is runing to connect 
        raise Exception('Failed to boot, instance status: %s' % str(instance_status))

    print('..Online')

    return instance, profile


def check_instance_initialization(instance_id, client=None, region=None, instance_wait_sleep=5): 
    '''Check if the instance has passed the intialization phase'''

    if client is None: 
        try: assert region is not None
        except: raise Exception('If client is None region must be passed.')
        # Connect to aws ec2 subnet as a client 
        client = boto3.client('ec2', region_name=region)                
    
    attempt = 0 
    instance_up = False
    
    while not instance_up:
        try: 
            sys.stdout.write(".")
            sys.stdout.flush() 
            instance_status = client.describe_instance_status(InstanceIds=[instance_id])['InstanceStatuses'][0]['InstanceStatus']['Status']
            if instance_status!='initializing':
                instance_up=True        
            else:
                if attempt==0:
                    sys.stdout.write('\nWaiting for instance to boot...')   
                    sys.stdout.flush()  
                time.sleep(instance_wait_sleep)
                attempt+=1
        except Exception as e:
            raise e
            sys.stdout.write(".")
            sys.stdout.flush() 
            time.sleep(2)        

    return instance_status


def connect_to_instance(ip, keyfile, username='ec2-user', port=22, timeout=10):
    '''
    Connect to the spot instance using paramiko's SSH client 
    __________
    parameters
    - ip : string. public IP address for the instance 
    - keyfile : string. name of the private key file 
    - username : string. username used to log-in for the instance. This will usually depend on the operating system of the image used. For a list of operating systems and defaul usernames check https://alestic.com/2014/01/ec2-ssh-username/
    - port : int. the ingress port to use for the instance 
    - timeout : int. the number of seconds to wait before giving up on a connection attempt  
    '''
    
    ssh_client = paramiko.SSHClient()                                          # Instantiate the SSH Client
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy)             # Policy for automatically adding the hostname and new host key to the local `.HostKeys` object, and saving it. 
    k = paramiko.RSAKey.from_private_key_file(keyfile+'.pem')                  # Create an RSA key from the key file to avoid runtime 

    retries = 0 
    connected = False 

    sys.stdout.flush() 
    while connected==False: 
        try:
            # use the public IP address to connect to an instance over the internet, default username is ubuntu
            ssh_client.connect(ip, username=username, pkey=k, port=port, timeout=timeout)
            connected = True
            break
        except Exception as e:
            retries+=1 
            sys.stdout.write(".")
            sys.stdout.flush() 
            if retries>=5: 
                raise e  

    return ssh_client
   