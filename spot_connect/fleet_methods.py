'''
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot-connect

LinkAWS Class:

Class to quickly perform data syncronization and distributed tasks on AWS 
infrastructure using the spotted module. 

MIT License 2020
'''

import os, sys, boto3
from path import Path 

root = Path(os.path.dirname(os.path.abspath(__file__)))

from spot_connect import iam_methods

    

def launch_spot_fleet(account_number,
                      n_instances, 
                      profile, 
                      name=None,
                      user_data=None, 
                      instance_profile='',
                      monitoring=True,
                      availability_zone=None,
                      kp_dir=None,
                      enable_nfs=True,
                      enable_ds=True):
    '''
    Launch a spot fleet request 
    '''
        
    client = boto3.client('ec2', region_name=profile['region'])

    #~#~#~#~#~#~#~#~#~#~#
    #~#~# Key Pairs #~#~#
    #~#~#~#~#~#~#~#~#~#~#
    
    if 'key_pair' not in profile: 
        if name is None: 
            raise Exception('key_pair not in profile. Please use name arg to create a key-pair & security group')        
        # Log a keypair in the profile directory
        profile['key_pair']=('KP-'+name, 'KP-'+name+'.pem')
        
    try: 
        iam_methods.create_key_pair(client, profile, kp_dir)
    except Exception as e: 
        if 'InvalidKeyPair.Duplicate' in str(e):
            print('Key pair detected, re-using...')
        else: 
            sys.stdout.write('Was not able to find Key-Pair in default directory '+str(kp_dir))
            sys.stdout.write("\nTo reset default directory run: spot_connect.sutils.set_default_kp_dir(<dir>)")
            sys.stdout.flush()   
            raise e 
            
    #~#~#~#~#~#~#~#~#~#~#~#~#~#
    #~#~# Security Groups #~#~#
    #~#~#~#~#~#~#~#~#~#~#~#~#~#
            
    # If no security group was submitted 
    if 'security_group' not in profile:                                                    
        if name is None: 
            raise Exception('key_pair not in profile. Please use name arg to create a key-pair & security group')        
        # Create and retrieve the security group 
        sg = iam_methods.get_security_group(client, 'SG-'+name, enable_nfs=enable_nfs, enable_ds=enable_ds, firewall_ingress_settings=profile['firewall_ingress'])    

        # For the profile we need a tuple of the security group ID and the security group name. 
        profile['security_group'] = (sg['GroupId'],'SG-'+name)               # Add the security group ID and name to the profile dictionary 

    #~#~#~#~#~#~#~#~#~#~#~#~#~#
    #~#~# Fleet Requests  #~#~#
    #~#~#~#~#~#~#~#~#~#~#~#~#~#

    launch_specs = [{
        'SecurityGroups':[
            {
                'GroupId':profile['security_group'][0]
            }
        ],
        'EbsOptimized': False,                   # do not optimize for EBS storage 
        'ImageId': profile['image_id'],          # AWS image ID. List available programatically or through launch wizard 
        'InstanceType': profile['instance_type'],# Instance type. List available programatically or through wizard or at https://aws.amazon.com/ec2/spot/pricing/ 
        'KeyName': profile['key_pair'][0],       # Name for the key pair
        'Monitoring' : {'Enabled': monitoring},  # Enable monitoring
    }]
    
    if instance_profile!='':
        launch_specs[0]['IamInstanceProfile']= {                              # Define the IAM role for your instance 
                     'Name': instance_profile,                                       
        }
    if user_data is not None: 
        launch_specs[0]['UserData']= user_data
    if availability_zone is not None: 
        launch_specs[0]['Placement']= {
                'AvailabilityZone': availability_zone, 
        }
        
    response = client.request_spot_fleet(
        DryRun=False,
        SpotFleetRequestConfig={
            'TargetCapacity': n_instances,
            'IamFleetRole': 'arn:aws:iam::'+account_number+':role/aws-ec2-spot-fleet-tagging-role',  # required 
            'LaunchSpecifications': launch_specs
        }
    )
        
    return response


def get_fleet_instances(spot_fleet_req_id, region=None):
    '''Returns a list of dictionaries where each dictionary describes an instance under the given fleet'''
    if region is None: 
        client = boto3.client('ec2')
    else: 
        client = boto3.client('ec2', region_name=region)
    return client.describe_spot_fleet_instances(SpotFleetRequestId=spot_fleet_req_id)