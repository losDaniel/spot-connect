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

import boto3, paramiko, time, sys 

from spot_connect import spot_utils 

key_pair_directory = spot_utils.get_default_kp_dir()

def launch_spot_instance(spotid, 
                         profile, 
                         instance_profile='', 
                         monitoring=True, 
                         spot_wait_sleep=5, 
                         instance_wait_sleep=5, 
                         kp_dir=key_pair_directory, 
                         enable_nfs=True, 
                         enable_ds=True):
    '''
    Launch a spot instance using the preconfigured aws account on boto3. Returns instance ID. 
    __________
    parameters 
    - spotid : name for the spot instance 
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
    '''

    # Connect to aws ec2 subnet as a client 
    client = boto3.client('ec2', region_name=profile['region'])                
    
    #~#~#~#~#~#~#~#~#~#~#
    #~#~# Key Pairs #~#~#
    #~#~#~#~#~#~#~#~#~#~#

    # If no key_par exists for the current spot instance id
    if 'key_pair' not in profile:                                               
        # Log a keypair in the profile dictionary 
        profile['key_pair']=('KP-'+spotid,'KP-'+spotid+'.pem')                 

    try: 
        # Create a key pair on AWS
        keypair = client.create_key_pair(KeyName=profile['key_pair'][0])       
        
        # Download the private key into the CW
        with open(kp_dir+'/'+profile['key_pair'][1], 'w') as file:             
            file.write(keypair['KeyMaterial'])
            file.close()
        print('Key pair created...')

    except Exception as e: 

        if 'InvalidKeyPair.Duplicate' in str(e): 
            print('Key pair detected, re-using...')
        else: 
            sys.stdout.write("Was not able to find Key-Pair in default directory "+str(kp_dir))
            sys.stdout.write("\nTo reset default directory run: stop_aws.spot_utils.set_default_kp_dir(<dir>)")
            sys.stdout.flush()   
            raise e 

    #~#~#~#~#~#~#~#~#~#~#~#~#~#
    #~#~# Security Groups #~#~#
    #~#~#~#~#~#~#~#~#~#~#~#~#~#

    # If no security group was submitted 
    if 'security_group' not in profile:                                        
        
        try: 
            # Create a security group for the current spot instance id 
            sg = client.create_security_group(GroupName='SG-'+spotid,          
                                              Description='SG for '+spotid)
            
            if enable_nfs:                                                     
                # Add NFS rules (port 2049) in order to connect an EFS instance 
                client.authorize_security_group_ingress(GroupName='SG-'+spotid,
                                                        IpPermissions=[
                                                                {'FromPort': 2049,
                                                                 'IpProtocol': 'tcp',
                                                                 'IpRanges': [{'CidrIp': '0.0.0.0/0'}],
                                                                 'ToPort': 2049,
                                                                }
                                                        ])   
            
            if enable_ds:                                                      
                # Add ingress & egress rules to enable datasync
                # Add HTTP and HTTPS rules (port 80 & 443) in order to connect to datasync agent
                client.authorize_security_group_ingress(GroupName='SG-'+spotid,
                                                        IpPermissions=[
                                                                {'FromPort': 80,
                                                                 'IpProtocol': 'tcp',
                                                                 'IpRanges': [{'CidrIp': '0.0.0.0/0'}],
                                                                 'ToPort': 80,
                                                                },
                                                                {'FromPort': 443,
                                                                 'IpProtocol': 'tcp',
                                                                 'IpRanges': [{'CidrIp': '0.0.0.0/0'}],
                                                                 'ToPort': 443,
                                                                }                                        
                                                        ])

                # Add HTTPS egress rules (port 443) in order to connect datasync agent instance to AWS 
                client.authorize_security_group_egress(GroupId=sg['GroupId'],  
                                                        IpPermissions=[
                                                                {'FromPort': 443,
                                                                 'IpProtocol': 'tcp',
                                                                 'IpRanges': [{'CidrIp': '0.0.0.0/0'}],
                                                                 'ToPort': 443,
                                                                }                                        
                                                        ]) 

            # Define ingress rules OTHERWISE YOU WILL NOT BE ABLE TO CONNECT
            if 'firewall_ingress' in profile:                                  
                client.authorize_security_group_ingress(GroupName='SG-'+spotid,
                                                        IpPermissions=[
                                                                {'FromPort': profile['firewall_ingress'][1],
                                                                 'IpProtocol': profile['firewall_ingress'][0],
                                                                 'IpRanges': [
                                                                         {'CidrIp': profile['firewall_ingress'][3],
                                                                          'Description': 'ips'
                                                                          },
                                                                          ],
                                                                'ToPort': profile['firewall_ingress'][2],
                                                                }
                                                        ])

            if 'firewall_egress' in profile:
                # TODO : parameters for sg_egress and applplication to client.authorize_security_group_egress (Not necessary to establish a connection)
                pass            

            sys.stdout.write("Security Group Created...")
            sys.stdout.flush()  
            
        except Exception as e:
            
            if 'InvalidGroup.Duplicate' in str(e): 
                print('Security group detected, re-using...')
                sg = client.describe_security_groups(Filters=[{'Name':'group-name','Values':['SG-'+spotid]}])['SecurityGroups'][0]
            else: 
                raise e 
            
        profile['security_group'] = (sg['GroupId'],'SG-'+spotid)               # Add the security group ID and name to the profile dictionary 

    #~#~#~#~#~#~#~#~#~#~#~#~#~#~#
    #~#~# Instance Requests #~#~#
    #~#~#~#~#~#~#~#~#~#~#~#~#~#~#

    # Retrieve current active or open spot instance requests under the current security group
    spot_requests = client.describe_spot_instance_requests(Filters=[{'Name':'launch.group-id', 'Values':[profile['security_group'][0]]},
                                                                     {'Name':'state','Values':['open','active']}])['SpotInstanceRequests']
    
    # If there are open/active instance requests with the same name (should only be one) re-use the first one that was found 
    if len(spot_requests)>0:                                                   
        spot_req_id = spot_requests[0]['SpotInstanceRequestId']                

    else:
        # Otherwise request a new one 
        sys.stdout.write('Requesting spot instance')
        sys.stdout.flush()  

        response = client.request_spot_instances(                              
            AvailabilityZoneGroup=profile['region'],
            ClientToken=spotid,                                                # submit a name to ensure idempotency 
            DryRun=False,                                                      # if True, checks if you have permission without actually submitting request
            InstanceCount=1,                                                   # number of individual instances 
            LaunchSpecification={
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
                'IamInstanceProfile' : {                                       # Define the IAM role for your instance 
                        'Name': instance_profile,                                       
                },
            },
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
    while not instance_id:                                                     
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

    sys.stdout.write('Retrieving instance by id')
    sys.stdout.flush()             

    try: 
        reservations = client.describe_instances(InstanceIds=[instance_id])['Reservations']
        instance = reservations[0]['Instances'][0]                             

    except Exception as e: 
        raise e 
        
    sys.stdout.write('Got instance: '+str(instance['InstanceId'])+'['+str(instance['State']['Name'])+']')
    sys.stdout.flush() 
    
    attempt = 0 
    instance_up = False

    # Check if the instance has started-up
    while not instance_up:

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
    if instance_status!='ok':                                                  # Wait until the instance is runing to connect 
        raise Exception('Failed to boot, instance status: %s' % str(instance_status))

    sys.stdout.write('..Online')
    sys.stdout.flush()   

    return instance, profile


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
   