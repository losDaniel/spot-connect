"""
Launch and connect to spot instances

Example execution from windows command prompt: 
    $ cd ./Spot-Instance-AWS
    $ python spot_connect.py -n test -p default -s test.sh

Update of https://peteris.rocks/blog/script-to-launch-amazon-ec2-spot-instances/

Imports: Script will install non-native requirements automatically 
"""
try:
    import paramiko
except:
    import pip
    pip.main(['install', 'paramiko'])    
    import paramiko    
try:
    from netaddr import IPNetwork
except:
    import pip
    pip.main(['install', 'netaddr'])    
    from netaddr import IPNetwork
try:
    import boto3
except:
    import pip
    pip.main(['install', 'netaddr'])    
    import boto3
import time, os, sys, argparse 



def launch_spot_instance(spotid, profile, spot_wait_sleep=5, instance_wait_sleep=5, key_pair_dir=os.getcwd(), enable_nfs=True):
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
    - spot_wait_sleep : how much time to wait between each probe of whether the spot request has been placed 
    - instance_wait_sleep : how much time to wait between each probe of whether the spot request has been filled
    '''

    client = boto3.client('ec2', region_name=profile['region'])                # Connect to ec2 cloud instance 
    
    if 'key_pair' not in profile:                                              # If no key_par exists for the current spot instance id 
        profile['key_pair']=('KP-'+spotid,'KP-'+spotid+'.pem')                 # Log a keypair in the profile dictionary 
    try: 
        print('Creating key pair...')
        keypair = client.create_key_pair(KeyName=profile['key_pair'][0])       # Create a key pair on AWS
        with open(key_pair_dir+'/'+profile['key_pair'][1], 'w') as file:       # Download the private key into the CW
            file.write(keypair['KeyMaterial'])
            file.close()
        print('...created')
    except Exception as e: 
        if 'InvalidKeyPair.Duplicate' in str(e): 
            print('...already exists')
        else: 
            raise e 

    if 'security_group' not in profile:                                        # If no security group was submitted 
        try: 
            print('Creating security group...')
            sg = client.create_security_group(GroupName='SG-'+spotid,          # Create a security group for the current spot instance id 
                                              Description='SG for '+spotid)
            if enable_nfs: 
                client.authorize_security_group_ingress(GroupName='SG-'+spotid,# Add NFS rules (port 2049) in order to connect an EFS instance 
                                                        IpPermissions=[
                                                                {'FromPort': 2049,
                                                                 'IpProtocol': 'tcp',
                                                                 'IpRanges': [{'CidrIp': '0.0.0.0/0'}],
                                                                 'ToPort': 2049,
                                                                }
                                                        ])   
            if 'firewall_ingress' in profile:                                  # Define ingress rules OTHERWISE YOU WILL NOT BE ABLE TO CONNECT
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
            print('...created')
        except Exception as e:
            if 'InvalidGroup.Duplicate' in str(e): 
                print('...already exists')
                sg = client.describe_security_groups(Filters=[{'Name':'group-name','Values':['SG-'+spotid]}])['SecurityGroups'][0]
            else: 
                raise e 
            
        profile['security_group'] = (sg['GroupId'],'SG-'+spotid)               # Add the security group ID and name to the profile dictionary 

    # Retrieve current active or open spot instance requests under the current security group
    spot_requests = client.describe_spot_instance_requests(Filters=[{'Name':'launch.group-id', 'Values':[profile['security_group'][0]]},
                                                                     {'Name':'state','Values':['open','active']}])['SpotInstanceRequests']
    
    if len(spot_requests)>0:                                                   # If there are open/active instance requests  
        print('Existing unresolved spot requests')
        print('Reusing existing spot request')
        spot_req_id = spot_requests[0]['SpotInstanceRequestId']                # Re-use the first one that was found 
    else:
        print('Requesting spot instance')                                      
        response = client.request_spot_instances(                              # Otherwise request a new one 
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
            },
            SpotPrice=profile['price'],                                        # Must be greater than current instance type price for region, available at https://aws.amazon.com/ec2/spot/pricing/ 
            Type='one-time',                                                   # Persisitence is usually not necessary (given storage backup) or advisable with spot instances 
        )
        spot_req_id = response['SpotInstanceRequests'][0]['SpotInstanceRequestId']
    # check if the instance id has been created (if the instance has been created)
    print('Initializing...')
    instance_id = None
    spot_tag_added = False
    while not instance_id:                                                     # Wait for the instance to initialize
                                                                               # Retrieve the request by ID 
        spot_req = client.describe_spot_instance_requests(Filters=[{'Name':'spot-instance-request-id', 'Values':[spot_req_id]}])['SpotInstanceRequests']
        if len(spot_req)>0:          
            spot_req = spot_req[0]                                             
            if not spot_tag_added:                                             # If no tag has been added yet add a tag to the request with the spot instance name 
                client.create_tags(Resources=[spot_req['SpotInstanceRequestId']], Tags=[{'Key':'Name','Value':spotid}])
                spot_tag_added=True
            if spot_req['State']=='failed':                                    # If the request failed raise an exception 
                raise Exception('Spot Request Failed')
            if 'InstanceId' in spot_req:                                       # If an instance ID was returned with the spot request we exit the while loop 
                instance_id = spot_req['InstanceId']
            else: 
                print('.')                                             # Otherwise we continue to wait 
                time.sleep(spot_wait_sleep)
        else: 
            print('.')                                                 # If a new spot request was submitted it may take a moment to register
            time.sleep(spot_wait_sleep)                                        # Wait and attempt to connect again 

    print('Retrieving instance by id')
    try: 
        reservations = client.describe_instances(InstanceIds=[instance_id])['Reservations']
        instance = reservations[0]['Instances'][0]                             
    except Exception as e: 
        raise Exception('Request not submitted')

    print('Got instance: '+str(instance['InstanceId'])+'['+str(instance['State']['Name'])+']')
    print('Waiting for instance to boot')
    while not instance['State']['Name'] in ['running','terminated','shutting-down']:
        print('.')
        time.sleep(instance_wait_sleep)
        reservations = client.describe_instances(InstanceIds=[instance_id])['Reservations']
        instance = reservations[0]['Instances'][0]
    if instance['State']['Name']!='running':                                   # Wait until the instance is runing to connect 
        raise Exception('Instance was terminated')
    print('Online')

    return instance, profile                                                   # Return the instance and profile in case a key and security group were added to the profile 



def connect_to_instance(ip, keyfile, username='ubuntu', port=22, timeout=10):
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
    print('Connecting...')
    while connected==False: 
        try:
            # use the public IP address to connect to an instance over the internet, default username is ubuntu
            ssh_client.connect(ip, username=username, pkey=k, port=port, timeout=timeout)
            connected = True
            break
        except Exception as e:
            retries+=1 
            print('.')
            if retries>=5: 
                raise e  
    print('Connected')
    return ssh_client



def launch_efs(system_name, region='us-west-2', launch_wait=3):
    '''
    Connect to an existing file system 
    '''
    client = boto3.client('efs', region_name=region)
    
    file_systems = client.describe_file_systems(CreationToken=system_name)['FileSystems']                    
    if len(file_systems)==0:                                                   # If there are no file systems with the `system_name` 
        print('Creating EFS file system...')
        client.create_file_system(                                             # Create the file system 
            CreationToken=system_name,
            PerformanceMode='generalPurpose',
        )
        initiated=False 
        print('Initializing...')
        while not initiated:                                                   # Wait until the file system is detectable 
            try: 
                file_system = client.describe_file_systems(CreationToken=system_name)['FileSystems'][0]
            except: 
                print('.')
                time.sleep(launch_wait)
        print('detected')
    else: 
        print('EFS file system already exists...')
        file_system = file_systems[0]                                          # If the file system exists 
                
    return file_system 



def retrieve_efs_mount(file_system_name, instance, region='us-west-2', mount_wait=3): 
    
    file_system = launch_efs(file_system_name, region=region)                  # Launch or connect to an EFS 
    file_system_id = file_system['FileSystemId']
        
    client = boto3.client('efs', region_name='us-west-2')                      # Connect and check for existing mount targets on the EFS  
    mount_targets = client.describe_mount_targets(FileSystemId=file_system_id)['MountTargets']
    if len(mount_targets)==0:                                                  # If no mount targets are detected on the file system
        print('No mount target detected. Creating mount target...')
        subnet_id = instance['SubnetId']                                       # Gather the instance subnet ID. Subnets are your personal cloud, for a full explanation see https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Subnets.html
        security_group_id = instance['SecurityGroups'][0]['GroupId']           # Get the instance's security group 
        
        ec2 = boto3.resource('ec2')                                            
        subnet = ec2.Subnet(subnet_id)                                         # Get the features of the subnet
        net = IPNetwork(subnet.cidr_block)                                     # Get the IPv4 CIDR block assigned to the subnet.
        ips = [str(x) for x in list(net[4:-1])]                                # The CIDR block is a block or range of IP addresses, we only need to assign one of these to a single mount
    
        response = client.create_mount_target(                                 # Create the mount target 
            FileSystemId=file_system_id,                                       # Under the file system just created 
            SubnetId=subnet_id,                                                # Under the same subnet as the EC2 instance you've just created 
            IpAddress=ips[0],                                                  # Assign it the first IP Adress from the CIDR block assigned to the subnet 
            SecurityGroups=[
                security_group_id,                                             # Apply the security group which must have ingress rules to allow NFS client connections (enable port 2049)
            ]
        )
        initiated = False
        print('Initializing...')
        while not initiated: 
            try:                                                               # Probe for the mount target until it is detectable 
                mount_target = client.describe_mount_targets(MountTargetId=response['MountTargetId'])['MountTargets'][0]
                initiated = True 
            except: 
                print('.')
                time.sleep(mount_wait)
        print('detected')
    else: 
        mount_target = mount_targets[0]
    
    instance_dns = instance['PublicDnsName']
    filesystem_dns = file_system_id+'.efs.'+region+'.amazonaws.com'
    
    with open('efs_mount.sh','w') as f:                                        # how to mount EFS on EC2: https://docs.aws.amazon.com/efs/latest/ug/wt1-test.html
        f.write('sudo yum -y install nfs-utils'+'\n')
        f.write('mkdir ~/efs-mount-point'+'\n')
        f.write('sudo mount -t nfs -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport '+filesystem_dns+':/   ~/efs-mount-point '+'\n')
        f.write('cd ~/efs-mount-point'+'\n')
        f.write('sudo chmod go+rw .'+'\n')
        f.close() 
            
    return mount_target, instance_dns, filesystem_dns



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



def run_script(instance, user_name, script_file, port=22):
    '''
    Run a script on the the given instance 
    __________
    parameters
    - instance : dict. Response dictionary from ec2 instance describe_instances method 
    - user_name : string. SSH username for accessing instance, default usernames for AWS images can be found at https://alestic.com/2014/01/ec2-ssh-username/
    - port : port to use to connect to the instance 
    - script_file : string. ".sh" file or linux/unix command (or other os resource) to execute on the instance command line 
    '''
    script = open(script_file, 'r').read().replace('\r', '')
    
    client = connect_to_instance(instance['PublicIpAddress'],instance['KeyName'],username=user_name,port=port)
    session = client.get_transport().open_session()
    session.set_combine_stderr(True)                                           # Combine the error message and output message channels

    session.exec_command(script)                                               # Execute a command or .sh script (unix or linux console)
    stdout = session.makefile()                                                # Collect the output 
    try:
        for line in stdout:
            print(line.rstrip())                                               # Show the output 
    except (KeyboardInterrupt, SystemExit):
        print(sys.stderr, 'Ctrl-C, stopping')
    client.close()                                                             # Close the connection 
    exit_code = session.recv_exit_status()
    print(sys.stderr, 'Exit code: ' + str(exit_code))
    return exit_code == 0



if __name__ == '__main__':                                                     # Main execution 
    
    profiles={
            "default": {'firewall_ingress': ('tcp', 22, 22, '0.0.0.0/0'),      # Must define a firewall ingress rule in order to connect to an instance 
                        'image_id':'ami-0859ec69e0492368e',                    # Image ID from AWS. go to the launch-wizard to get the image IDs or use the boto3 client.describe_images() with Owners of Filters parameters to reduce wait time and find what you need.
                        'instance_type':'t2.micro',                            # Get a list of instance types and prices at https://aws.amazon.com/ec2/spot/pricing/ 
                        'price':'0.004',
                        'region':'us-west-2',
                        'scripts':['efs_mount.sh'],                            # By default, execute the bash script to mount the EFS file storage on the spot instance 
                        'username':'ec2-user',                                 # This will usually depend on the operating system of the image used. For a list of operating systems and defaul usernames check https://alestic.com/2014/01/ec2-ssh-username/
                        }
            }
    
    parser = argparse.ArgumentParser(description='Launch spot instance')
    parser.add_argument('-n', '--name', help='Name of the spot instance', required=True)
    parser.add_argument('-p', '--profile', help='Profile', default=list(profiles.keys())[0], choices=profiles.keys())
    parser.add_argument('-s', '--script', help='Script path', action='append', default=[])
    args = parser.parse_args()
    
    profile = profiles[args.profile]
    
    try:                                                   
        instance, profile = launch_spot_instance(args.name, profile)           # Launch or connect to the spot instance under the given name 
    except Exception as e:
        raise e
        sys.exit(1)
        
    try:                                                                       # Create and/or mount an EFS to the instance 
        mount_target, instance_dns, filesystem_dns = retrieve_efs_mount(args.name, instance)
    except Exception as e: 
        raise e 
        sys.exit(1)        

    for script in profile['scripts'] + args.script:
        if not run_script(instance, profile['username'], script):
            break

        
        
        
        
        
        
        
        
        
        
        
        
        
        