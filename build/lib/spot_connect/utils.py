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

import os, ast, boto3
from path import Path 


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
    
    profile = [f for f in list(absoluteFilePaths(pull_root())) if f.split('\\')[-1]=='profiles.txt'][0]    
    
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
    kpfile = [f for f in list(absoluteFilePaths(pull_root())) if f.split('\\')[-1]=='profiles.txt'][0]    
    with open(kpfile,'r') as f: 
        default_path = f.read()
        f.close()
    return default_path 

def get_default_kp_dir(): 
    '''Get the default key pair directory'''    
    kp_dir = get_package_kp_dir()                             
    if kp_dir =='': 
        raise Exception('Please use the "set_default_kp_dir" method to set a default key-pair storage directory. You only need to do this once.')
    return kp_dir

def set_default_kp_dir(directory : str): 
    '''Set the default key pair directory'''
    kpfile = [f for f in list(absoluteFilePaths(pull_root())) if f.split('\\')[-1]=='key_pair_default_dir.txt'][0]    
    with open(kpfile,'w') as f: 
        f.write(directory)
        f.close()
    print('Default path has been set to '+kpfile)    


if __name__ == '__main__':
    pull_root()
    try: 
        directory = get_package_kp_dir()
        print('Default key-pair directory is %s' % directory)
    except: 
        directory = input('Please select a default directory in which to save your key-pairs.')
        print('Setting %s as the default key-pair directory, you can change it using spot_connect.utils.set_default_kp_dir(<new directory>)' % directory)