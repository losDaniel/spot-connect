
"""
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot_aws 

Launch and connect to spot instances

Examples: 
  Spot instance launch from windows command prompt: 
       $ cd ./Spot-Instance-AWS
       $ python spot_connect.py -n test -p default -s test.sh

  Datasync spot instance from windows command prompt: 
       $ cd ./Spot-Instance-AWS
       $ python spot_connect.py -n datasync -p datasync 
    
Notes: 
  <datasync>: Run datasync and spot instance under the same regions but with different names, the datasync requires a special AMI that needs its own instance.
              If `enable_nfs` and `enable_ds` are True when each is launched under different names, instances should still be able to interact with one another. 

  <configuration>: the aws client has already been configured using the awscli through the anaconda prompt.   
                   To do this `pip install awscli` and from the anaconda (or other python prompt) run `aws config` and follow the prompts.  

References: 
  Part of this project is a direct update for use with boto3 of https://peteris.rocks/blog/script-to-launch-amazon-ec2-spot-instances/ 
    
**Imports: Script will install non-native requirements automatically 

MIT License
"""

from path import Path 
import argparse, sys, time, os

root = Path(os.path.dirname(os.path.abspath(__file__)))

from spot_connect import sutils, instances, methods, elastic_file_systems

def main():                                                     # Main execution 
    
    profiles=sutils.load_profiles()         

    parser = argparse.ArgumentParser(description='Launch spot instance')
    parser.add_argument('-n', '--name', help='Name of the spot instance', required=True)
    parser.add_argument('-p', '--profile', help='Profile', default=list(profiles.keys())[0], choices=profiles.keys())
    parser.add_argument('-s', '--script', help='Script path', default='')
    parser.add_argument('-f', '--filesystem', help='Elastic File System name', default='')
    parser.add_argument('-u', '--upload', help='File or directory to upload', default='')
    parser.add_argument('-r', '--remotepath', help='Directory on EC2 instance to upload via ordinary NFS', default='.')
    parser.add_argument('-a', '--activeprompt', help='If "True" leave an active shell open after running scripts', default=False)
    parser.add_argument('-t', '--terminate', help='Terminate the instance after running everything', default=False)
    parser.add_argument('-m', '--monitoring', help='Activate monitoring for the instance', default=True)
    parser.add_argument('-nm','--newmount', help='Create a new mount target even if one exists', default=False)
    parser.add_argument('-ip','--instanceprofile', help='Instance profile with attached IAM roles', default='')
    args = parser.parse_args()
    
    profile = profiles[args.profile]
    print('', flush=True)
    print('#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#', flush=True)
    print('#~#~#~#~#~#~#~# Launching '+args.name, flush=True)
    print('#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#', flush=True)
    print('', flush=True)
    
    try: 
        kp_dir = sutils.get_package_kp_dir() 
        if kp_dir =='': 
            raise Exception   
        print('Default key-pair directory is "%s"' % kp_dir)
    except: 
        kp_dir = input('Please select a default directory in which to save your key-pairs: ')
        sutils.set_default_kp_dir(kp_dir)
        print('You can change the default key-pair directory using spot_connect.sutils.set_default_kp_dir(<dir>)' % kp_dir)

    # Add a forward slash to the kp_dir 
    if kp_dir[-1]!='/':
        kp_dir = kp_dir + '/'

    # Launch the instance using the name profile, instance profile and monitoring arguments     
    try:                                                   
        instance, profile = instances.launch_spot_instance(args.name, profile, instance_profile=args.instanceprofile, monitoring=args.monitoring, kp_dir=kp_dir)  # Launch or connect to the spot instance under the given name 
    except Exception as e:
        raise e
        sys.exit(1)

    if profile['efs_mount']: 
        
        # If no filesystem name is submitted then do not attach a file system 
        if args.filesystem=='':       
            print('No EFS mount requested for this instance.')                                         
            pass

        # Otherwise create the file system and attach an efs mount. 
        else: 
            print('Profile requesting EFS mount...')
        
            fs_name = args.filesystem                                          

            try:                                                               # Create and/or mount an EFS to the instance 
                mount_target, instance_dns, filesystem_dns = elastic_file_systems.retrieve_efs_mount(fs_name, instance, new_mount=args.newmount)
            except Exception as e: 
                raise e 
                sys.exit(1)        
            print('Connecting to instance to link EFS...')
            methods.run_script(instance, profile['username'], elastic_file_systems.compose_mount_script(filesystem_dns), cmd=True)
            
    st = time.time() 

    if args.upload!='':        
        files_to_upload = [] 
        for file in args.upload.split(','):
            files_to_upload.append(os.path.abspath(file))
        methods.upload_to_ec2(instance, profile['username'], files_to_upload, remote_dir=args.remotepath)    

    print('Time to Upload: %s' % str(time.time()-st))

    st = time.time() 
    
    scripts_to_run = []
    if args.script!= '': 
        for s in args.script.split(','):
            scripts_to_run.append(s)

    for script in profile['scripts'] + scripts_to_run:
        print('\nExecuting script "%s"...' % str(script))
        try:
            if not methods.run_script(instance, profile['username'], script):
                break
        except Exception as e: 
            print(str(e))
            print('Script %s failed with above error' % script)

    print('Time to Run Scripts: %s' % str(time.time()-st))
    
    if args.activeprompt:
        methods.active_shell(instance, profile['username'])

    if args.terminate:                                                         # If we want to terminate the instance 
        methods.terminate_instance(instance['InstanceId'])                             # termination overrrides everything else 
        print('Script %s has been terminated' % str(args.name))
