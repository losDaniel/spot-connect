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

import os, ast, boto3, random, string, pprint, glob, re
import pandas as pd 
from path import Path 
from IPython.display import clear_output

def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def genrs(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def absoluteFilePaths(directory):
    '''Get the absolute file path for every file in the given directory'''

    for dirpath,_,filenames in os.walk(directory):
        for f in filenames:
            yield os.path.abspath(os.path.join(dirpath, f))

def pull_root(): 
    '''Retrieve the directory for this instance'''
    return Path(os.path.dirname(os.path.abspath(__file__)))

def load_profiles():
    '''Load the profiles from the package profile.txt file'''
    
    profile = [f for f in list(absoluteFilePaths(pull_root()+'/data/')) if f.split('\\')[-1]=='profiles.txt'][0]    
    
    with open(profile,'r') as f:
        profiles = ast.literal_eval(f.read())
        
    #print('Profiles loaded, you can edit profiles in '+str(profile))
        
    return profiles

def default_region(): 
    profiles = load_profiles()
    print(profiles['default']['region'])       

def save_profiles(profiles):
    '''Save the profile dict str in a .txt file'''
    profile_file = [f for f in list(absoluteFilePaths(pull_root()+'/data/')) if f.split('\\')[-1]=='profiles.txt'][0]    
    
    #ptosave = ast.literal_eval(profile_str)
    print(profile_file)

    with open(profile_file,'w') as f:
        f.write(pprint.pformat(profiles))
        f.close()

def change_default_region(region, deactive_warning=True): 
    if not deactive_warning:
        ans = input('Warning: doing this will change the "region" for all profiles. Continue?(y): ')
        if ans!='y':
            raise Exception('User exit')

    profiles = load_profiles()
    for k in profiles: 
        profiles[k]['region'] = region

    save_profiles(profiles)

def change_default_image(image, deactive_warning=True): 
    if not deactive_warning:
        ans = input('Warning: doing this will change the "image_id" for all profiles. Continue?(y): ')
        if ans!='y':
            raise Exception('User exit')

    profiles = load_profiles()
    for k in profiles: 
        profiles[k]['image_id'] = image

    save_profiles(profiles)

def show_instances(): 
    client = boto3.client('ec2', region_name='us-west-2')
    print('Instances (by Key names):')
    for i in [res['Instances'][0] for res in client.describe_instances()['Reservations']]:
        print('     - "'+i['KeyName'].split('-')[1]+'" Type: '+i['InstanceType']+', ID: '+i['InstanceId'], flush=True)

def printTotals(transferred, toBeTransferred):
    '''Print paramiko upload transfer'''
    print("Transferred: %.3f" % float(float(transferred)/float(toBeTransferred)), end="\r", flush=True)

def get_package_kp_dir():
    '''Get the key-pair directory'''
    kpfile = [f for f in list(absoluteFilePaths(pull_root()+'/data/')) if f.split('\\')[-1]=='key_pair_default_dir.txt'][0]    
    with open(kpfile,'r') as f: 
        default_path = f.read()
        f.close()
    return default_path 

def get_default_kp_dir(): 
    '''Get the default key pair directory'''    
    kp_dir = get_package_kp_dir()
    return kp_dir

def set_default_kp_dir(directory : str): 
    '''Set the default key pair directory'''
    kpfile = [f for f in list(absoluteFilePaths(pull_root()+'/data/')) if f.split('\\')[-1]=='key_pair_default_dir.txt'][0]    
    with open(kpfile,'w') as f: 
        f.write(directory)
        f.close()
    print('Default path has been set to '+kpfile)    

def clear_key_pairs():
    '''Erase all the key pairs in the kp_directory'''
    answer = input('You are about to erase all the locally stored key pairs.\nYou will have to erase the matching key board through the AWS dashboard. Conitnue? (Y)')

    if answer == 'Y':
        for f in glob.glob(get_default_kp_dir()+'/*'):
            os.remove(f)
    else: 
        raise Exception('User exit')


def find_username(s):
    for k in username_dictionary:
        ios = re.findall('('+k+')',s)
        if len(ios)>0:
            ios = username_dictionary[ios[0]]
            break
        
    
    return ios


def select_region():
    for i,r in enumerate(ami_data['region'].unique()): print(i,r)
    region_idx = int(input('Enter the number of the region you want to set the profiles to'))
    region = list(ami_data['region'].unique())[region_idx]    
    clear_output()    
    return region 


def select_image(region):
    image_list = ami_data.loc[ami_data['region']==region, 'image_name']
    for i,r in enumerate(image_list):print(i,r)
    image_idx = int(input('Enter the number of the image you want to set the profiles to'))
    image_id = list(ami_data.loc[ami_data['region']==region, 'image_id'])[image_idx]    
    image_name =list(ami_data.loc[ami_data['region']==region, 'image_name'])[image_idx]    
    username = list(ami_data.loc[ami_data['region']==region, 'username'])[image_idx]    
    clear_output()    
    return image_id, image_name, username


def add_profile(profile_dict, instance_type, image_id, image_name, bid_price, min_price, region, username):
    profile_dict[instance_type]={
        'efs_mount': True,
        'firewall_ingress': ('tcp', 22, 22, '0.0.0.0/0'),
        'image_id': image_id,
        'image_name':image_name,
        'instance_type': instance_type,
        'price': bid_price,
        'min_price':min_price,
        'region': region,
        'scripts': [],
        'username': username
    }
    return profile_dict


def reset_profiles(price_increase=1.15):
    
    assert price_increase >= 1
    
    region = select_region()
    image_id, image_name, username = select_image(region)
    
    region_name = region.split(')')[0]+')'
    region_code = region.split(')')[1]
    spot_instance_pricing.loc[spot_instance_pricing['region']==region_name]

    profile_dict = {}
    for tup in spot_instance_pricing.itertuples():

        if 'N/A' in tup.linux_price:
            continue
        instance_price = float(re.findall('([0-9]*\.[0-9]*)',tup.linux_price)[0])
        bid_price = instance_price*price_increase

        profile_dict = add_profile(profile_dict, 
                                   tup.instance_type, 
                                   image_id, 
                                   image_name,
                                   bid_price,
                                   instance_price, 
                                   region_code, 
                                   username)

    save_profiles(profile_dict)

# Load the data needed for the module
username_dictionary = {'Linux':'ec2-user',
                       'Ubuntu':'ubuntu',
                       'Windows':'ec2-user'}

spot_instance_pricing = pd.read_csv(pull_root()+'/data/spot_instance_pricing.csv')
ami_data = pd.read_csv(pull_root()+'/data/ami_data.csv')
ami_data['username'] = ami_data['image_name'].apply(lambda s: find_username(s))
