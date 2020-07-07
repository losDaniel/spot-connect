
"""
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot_aws 

Launch and connect to spot instances

Examples: 
  Spot instance launch from windows command prompt: 
       $ python spot_connect -n test -p t3.micro 
    
Notes: 
  <configuration>: the aws client has already been configured using the awscli through the anaconda prompt.   
                   To do this `pip install awscli` and from the anaconda (or other python prompt) run `aws config` and follow the prompts.  
    
  <installing non-native packages on instances>: Use the scripts argument to submit bash scripts that can install non-native requirements automatically.

MIT License
"""

from path import Path 
import argparse, sys, time, os

root = Path(os.path.dirname(os.path.abspath(__file__)))

from spot_connect import sutils, ec2_methods, iam_methods, efs_methods, instance_methods

def main():                                                     # Main execution 
    
    profiles=sutils.load_profiles()         

    parser = argparse.ArgumentParser(description='Launch spot instance')

    # Variable for naming/identifying the instance
    parser.add_argument('-n',   '--name',       help='name for spot instance launch group (will be used as identifier)', default='')
    parser.add_argument('-iid', '--instanceid', help='instance id string (overrides --name)', default='')
    parser.add_argument('-kp',  '--keypair',    help='name of the key pair to use (will default to KP-<name> if none is submitted)', default='')
    parser.add_argument('-sg',  '--securitygroup', help='name of the security group to use (will default to SG-<name> if none is submitted)', default='')
    parser.add_argument('-ip',  '--instanceprofile', help='instance profile with attached IAM roles', default='')

    parser.add_argument('-p',   '--profile',    help='profile with efsmount, firewall, imageid, price, region, script and username settings any of which can be set here).', default=list(profiles.keys())[0], choices=profiles.keys())
    parser.add_argument('-em',  '--efsmount',   help='if True, will connect or create a filesystem (for internal use, if no filesystem name is submitted this will be False)', default=True)
    parser.add_argument('-fw',  '--firewall',   help='a tuple of len 4 with firewall settings', default='')
    parser.add_argument('-ami', '--imageid',    help='the ID for the AMI image to use', default='')
    parser.add_argument('-prc', '--price',      help='custom maximum price for the instance', default='')
    parser.add_argument('-reg', '--region',     help='AWS Region to use', default='')
    parser.add_argument('-s',   '--script',     help='script path (equivalent to user-date run on connection)', default='')
    parser.add_argument('-un',  '--username',   help='username to use to log into the instance, default is ec2-user', default='')

    parser.add_argument('-f',   '--filesystem', help='elastic file system creation token', default='')
    parser.add_argument('-nm',  '--newmount',   help='create a new mount target even if one exists (for internal use)', default=False)
    parser.add_argument('-u',   '--upload',     help='file or directory to upload', default='')
    parser.add_argument('-r',   '--remotepath', help='directory on EC2 instance to upload via ordinary NFS', default='.')
    parser.add_argument('-a',   '--activeprompt', help='if "True" leave an active shell open after running scripts', default=False)
    parser.add_argument('-t',   '--terminate',  help='terminate the instance after running everything', default=False)
    parser.add_argument('-m',   '--monitoring', help='activate monitoring for the instance', default=True)

    args = parser.parse_args()
    
    profile = profiles[args.profile]
 
    if args.instanceid != '': 
        spot_identifier = args.instanceid 
        using_id = True
    elif args.name == '': 
        raise Exception("Must submit a name <-n> or instance id <-iid>.")
    else: 
        spot_identifier = args.name
        using_id = False 
    
    print('', flush=True)
    print('#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#', flush=True)
    print('#~#~#~#~#~#~#~# Spotting '+spot_identifier, flush=True)
    print('#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#', flush=True)
    print('', flush=True)
        
    if args.keypair != '':
        profile['key_pair'] = (args.keypair, args.keypair+'.pem')
    
    if args.filesystem!='':
        print('Instance will be mounted on the '+args.filesystem+' elastic filesystem')
        profile['efs_mount'] = True
    elif args.filesystem=='':       
        print('No EFS mount requested for this instance.')                                         
        profile['efs_mount'] = False
    
    if args.firewall != '':
        profile['firewall_ingress'] = args.firewall
        
    if args.imageid != '': 
        profile['image_id'] = args.imageid
                
    if args.price != '': 
        profile['price'] = args.price
        
    if args.username != '': 
        profile['username'] = args.username     

    if args.region != '': 
        profile['region'] = args.region

    if args.securitygroup != '':
        # Retrieve the security group 
        sg = iam_methods.retrieve_security_group(args.securitygroup, region=profile['region'])    
        # For the profile we need a tuple of the security group ID and the security group name. 
        profile['security_group'] = (sg['GroupId'],args.securitygroup)          
    
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
    if kp_dir[-1]!='/': kp_dir = kp_dir + '/'

    # Launch the instance using the name profile, instance profile and monitoring arguments     
    try:         
        # If a key pair and security group were not added provided, they wil be created using the name of the instance                                
        instance, profile = ec2_methods.get_spot_instance(spot_identifier, profile, instance_profile=args.instanceprofile, monitoring=args.monitoring, kp_dir=kp_dir, using_instance_id=using_id)  # Launch or connect to the spot instance under the given name 
    except Exception as e:
        raise e
        sys.exit(1)

    # If a filesystem was provided and we want to mount an EFS 
    if profile['efs_mount']:         

        print('Requesting EFS mount...')    
        fs_name = args.filesystem                                          
        try:                                                               # Create and/or mount an EFS to the instance 
            mount_target, instance_dns, filesystem_dns = efs_methods.retrieve_efs_mount(fs_name, instance, new_mount=args.newmount, region=profile['region'])
        except Exception as e: 
            raise e 
            sys.exit(1)        
        print('Connecting to instance to link EFS...')
        instance_methods.run_script(instance, profile['username'], efs_methods.compose_mount_script(filesystem_dns), kp_dir=kp_dir, cmd=True)
            
    st = time.time() 

    if args.upload!='':        
        files_to_upload = [] 
        for file in args.upload.split(','):
            files_to_upload.append(os.path.abspath(file))
        instance_methods.upload_to_ec2(instance, profile['username'], files_to_upload, remote_dir=args.remotepath)    

        print('Time to Upload: %s' % str(time.time()-st))

    st = time.time() 
    
    scripts_to_run = []
    if args.script!= '': 
        for s in args.script.split(','):
            scripts_to_run.append(s)

    for script in profile['scripts'] + scripts_to_run:
        print('\nExecuting script "%s"...' % str(script))
        try:
            if not instance_methods.run_script(instance, profile['username'], script):
                break
        except Exception as e: 
            print(str(e))
            print('Script %s failed with above error' % script)

        print('Time to Run Script: %s' % str(time.time()-st))
    
    if args.activeprompt:
        instance_methods.active_shell(instance, profile['username'])

    if args.terminate:                                                         # If we want to terminate the instance 
        instance_methods.terminate_instance(instance['InstanceId'])                             # termination overrrides everything else 
        print('Instance %s has been terminated' % str(spot_identifier))
