"""
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot_aws 

General utility functions for spot_aws  

MIT License
"""

import os, ast, boto3
from path import Path 


def absoluteFilePaths(directory):
    '''Get the absolute file path for every file in the given directory'''

    for dirpath,_,filenames in os.walk(directory):
        for f in filenames:
            yield os.path.abspath(os.path.join(dirpath, f))


def load_profiles():
    '''Load the profiles from the package profile.txt file'''
    
    profile = [f for f in list(absoluteFilePaths(pull_root().parent)) if f.split('\\')[-1]=='profiles.txt'][0]    
    
    with open(profile,'r') as f:
        profiles = ast.literal_eval(f.read())
        
    print('Profiles loaded, you can edit profiles in '+str(profile))
        
    return profiles


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
    return pull_root().parent+'\\kp_dir\\'


def set_default_kp_dir(directory : str): 
    '''Set the default key pair directory'''

    # Get the package key pair path 
    kp_dir = get_package_kp_dir()                         

    # Write the defulat path to a text file in the package folder
    with open(kp_dir+'\\KP_default_path.txt', 'w') as f:   
        default_path = f.write(directory)            
        f.close()    
    print('Default path has been set to '+default_path)    


def get_default_kp_dir(): 
    '''Get the default key pair directory'''
    
    # Get the package key pair path 
    kp_dir = get_package_kp_dir()                         

    # If an alternative default path has been set then we can load there 
    if os.path.exists(kp_dir):        
        with open(kp_dir+'\\KP_default_path.txt', 'r') as f:
            default_path = f.read()
            f.close() 
    
    # Otherwise the package key-pair directory will work
    else: 
        default_path = kp_dir
    
    return default_path


def pull_root(): 
    '''Retrieve the directory for this instance'''
    return Path(os.path.dirname(os.path.abspath(__file__)))

    
if __name__ == '__main__':
    pull_root()