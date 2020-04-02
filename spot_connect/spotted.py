"""
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot-connect

Spotted module: 

The spotted class can implement all the functionality of spot_connect.py 
but it can be run from a notebook or python script.

MIT License 2020
"""

import sys, time, os, copy
from path import Path

root = Path(os.path.dirname(os.path.abspath(__file__)))

from spot_connect import sutils, instances, methods, elastic_file_systems

class SpotInstance: 
    
    profiles=sutils.load_profiles()         

    name = None 
    price = None 
    client = None
    region = None 
    kp_dir = None 
    profile = None 
    instance = None 
    username = None 
    key_pair = None 
    newmount = None 
    firewall = None 
    image_id = None 
    sec_group = None 
    efs_mount = None 
    monitoring = None 
    filesystem = None 
    mount_target = None 
    instance_dns = None 
    instance_type = None 
    filesystem_dns = None 
    filled_profile = None 
    instnace_profile = None
   
    def __init__(self,
                 name,
                 profile=None,
                 instance_profile=None,
                 monitoring=None,
                 filesystem=None,
                 image_id=None,
                 instance_type=None,
                 price=None,
                 region=None,
                 username=None,
                 key_pair=None,
                 kp_dir=None,
                 sec_group=None,
                 efs_mount=None,
                 newmount=None,
                 firewall=None):
        '''
        A class to run, control and interact with spot instances. 
        __________
        parameters
        - name : string. name of the spot instance
        - profile : dict of settings for the spot instance
        - monitoring : bool, default True. set monitoring to True for the instance 
        - filesystem : string, default <name>. creation token for the EFS you want to connect to the instance  
        - image_id : Image ID from AWS. go to the launch-wizard to get the image IDs or use the boto3 client.describe_images() with Owners of Filters parameters to reduce wait time and find what you need.
        - instance_type : Get a list of instance types and prices at https://aws.amazon.com/ec2/spot/pricing/ 
        - price : float. maximum price willing to pay for the instance. 
        - region : string. AWS region
        - username : string. This will usually depend on the operating system of the image used. For a list of operating systems and defaul usernames check https://alestic.com/2014/01/ec2-ssh-username/
        - key_pair : string. name of the keypair to use. Will search for `key_pair`.pem in the current directory 
        - sec_group : string. name of the security group to use
        '''

        self.name = name 
        self.client = None 
        
        self.profile = None         
        if profile is None: 
            self.profile=copy.deepcopy(SpotInstance.profiles['default'])            # create a deep copy so that the class dictionary doesn't get modified  
        else: 
            self.profile=copy.deepcopy(SpotInstance.profiles[profile])

        # Set directory in which to save the key-pairs
        self.kp_dir = None 
        if kp_dir is not None: 
            self.kp_dir = kp_dir
        else: 
            try: 
                kp_dir = sutils.get_package_kp_dir() 
                if kp_dir =='': 
                    raise Exception   
                print('Default key-pair directory is "%s"' % kp_dir)
                self.kp_dir = kp_dir
            except: 
                kp_dir = input('Please select a default directory in which to save your key-pairs: ')
                sutils.set_default_kp_dir(kp_dir)
                print('You can change the default key-pair directory using spot_connect.sutils.set_default_kp_dir(<dir>)' % kp_dir)
                self.kp_dir = kp_dir
        
        self.monitoring = None 
        if monitoring is None: 
            self.monitoring=True
        else: 
            self.monitoring=monitoring
        
        self.filesystem = None 
        if filesystem is None: 
            self.filesystem=''
        else:
            self.filesystem=filesystem
        
        self.newmount = None 
        if newmount is None:   
            self.newmount=False
        else:              
            self.newmount=newmount        
                
        self.efs_mount = None 
        if efs_mount is not None: 
            self.profile['efs_mount']=efs_mount
        
        self.firewall = None 
        if firewall is not None:
            self.profile['firewall']=firewall
        
        self.image_id = None 
        if image_id is not None:
            self.profile['image_id']=image_id
        
        self.instance_type = None 
        if instance_type is not None:
            self.profile['instance_type']=instance_type
        
        self.price = None 
        if price is not None:
            self.profile['price']=price
        
        self.region = None 
        if region is not None:
            self.profile['region']=region
        
        self.username = None 
        if username is not None:
            self.profile['username']=username
        
        self.key_pair = None 
        if key_pair is not None:
            self.profile['key_pair']=key_pair
            
        self.sec_group = None 
        if sec_group is not None:
            self.profile['security_group']=sec_group       
            
        if instance_profile is not None: 
            self.instance_profile=instance_profile
        else: 
            self.instance_profile = ''
               
        print('', flush=True)
        print('#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#', flush=True)
        print('#~#~#~#~#~#~#~# Spot Instance: '+self.name, flush=True)
        print('#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#', flush=True)
        print('', flush=True)
        
        self.filled_profile = None         

        try:                                     # Launch or connect to the spot instance under the given name
            # Returns the profile with any parameters that needed to be added automatically in order to connect (Key Pair and Security Group)                                                                 
            self.instance, self.filled_profile = instances.launch_spot_instance(self.name, self.profile, instance_profile=self.instance_profile, monitoring=self.monitoring, kp_dir=self.kp_dir)   
        except Exception as e:
            raise e
            sys.exit(1)
       
        print(self.filled_profile)
        print('')

        if self.filled_profile['efs_mount']: 
            print('Profile requesting EFS mount...')
            if self.filesystem=='':             # If no filesystem name is submitted 
                fs_name = self.name             # Retrieve or create a filesystem with the same name as the instance 
            else: 
                fs_name = self.filesystem     
            
            # Create and/or mount an EFS to the instance 
            try:                                
                self.mount_target, self.instance_dns, self.filesystem_dns = elastic_file_systems.retrieve_efs_mount(fs_name, self.instance, new_mount=self.newmount)
            except Exception as e: 
                raise e 
                sys.exit(1)        
                
            print('Connecting to instance to link EFS...')
            methods.run_script(self.instance, self.profile['username'], elastic_file_systems.compose_mount_script(self.filesystem_dns), kp_dir=self.kp_dir, cmd=True)
            
        if len(self.profile['scripts'])>0:
            methods.run_script(self.instance, self.profile['username'], self.profile['scripts'], kp_dir=self.kp_dir)

        self.state = self.instance['State']['Name']
        print('\nDone. Current instance state: '+self.state)
    
    
    def refresh_instance(self):
        '''Refresh the instance to get its current status & information'''
        if self.client is None: 
            client = boto3.client('ec2', region_name=self.profile['region'])

        reservations = client.describe_instances(InstanceIds=[self.instance['InstanceId']])['Reservations']
        self.instance = reservations[0]['Instances'][0]                             
        self.state = self.instance['State']['Name']
        print('Instance refreshed, current state: %s' % str(self.state))


    def upload(self, files, remotepath):
        '''
        Upload a file or list of files to the instance. If an EFS is connected to the instance files can be uploaded to the EFS through the instance. 
        __________
        parameters
        - files : str or list of str. file or list of files to upload
        - remotepath : str. path to upload files to, only one path can be specified. 
        '''
        if type(files)==str:
            files=[files]
        elif type(files)!=list: 
            raise TypeError('Files must but type str or list')

        st = time.time() 
            
        files_to_upload = [] 
        for file in files:
            files_to_upload.append(os.path.abspath(file))
        methods.upload_to_ec2(self.instance, self.profile['username'], files_to_upload, remote_dir=remotepath, kp_dir=self.kp_dir)    
    
        print('Time to Upload: %s' % str(time.time()-st))
        
        
    def download(self, files, localpath):
        '''
        Download a file or list of files from an instance. If an EFS is connected to the instance files can be uploaded to the EFS through the instance. 
        __________
        parameters
        - files : str or list of str. file or list of files to download (["/home/ec2-user/Day-Trader/aws/log_remote_1.txt","/home/ec2-user/Day-Trader/aws/log_remote_2.txt","/home/ec2-user/Day-Trader/aws/log_remote_3.txt"], os.getcwd()+'/data/outline_permutations/')
        - localpath : str or list of str. path to download files from, if list of str must be one-to-one with file list. 
        '''
        if type(files)==str: 
            files = [files]
            
        elif type(files)!=list: 
            raise TypeError('get must be str or list of str')

        if type(localpath) is str: 
            localpath = [localpath]*len(files)

        elif type(localpath)==list: 
            assert(len(localpath)==len(files))

        else: 
            raise TypeError('put must be str or list of str with equal length to `get`')

        st = time.time() 
            
        files_to_download = [] 
        for file in files:
            files_to_download.append(file)
        methods.download_from_ec2(self.instance, self.profile['username'], files_to_download, put=localpath, kp_dir=self.kp_dir)
    
        print('Time to Download: %s' % str(time.time()-st))


    def run(self, scripts, cmd=False, return_output=False, time_it=False):
        '''
        Run a script or list of scripts
        __________
        parameters
        - scripts : str or list of strings. list of scripts files to run 
        - cmd : if True, each script in scripts is treated as an individual command
        '''
        st = time.time() 
        
        if type(scripts)==str:
            scripts=[scripts]
        elif type(scripts)!=list:
            raise TypeError('scripts must be string or list of strings')
        
        for script in scripts:
            if not cmd:
                print('\nExecuting script "%s"...' % str(script))
            try:
                if return_output: run_stat, output = methods.run_script(self.instance, self.profile['username'], script, cmd=cmd, kp_dir=self.kp_dir, return_output=return_output)
                else: run_stat = methods.run_script(self.instance, self.profile['username'], script, cmd=cmd, kp_dir=self.kp_dir, return_output=return_output)

                if not run_stat:
                    break
            except Exception as e: 
                print(str(e))
                print('Script %s failed with above error' % script)
    
        if time_it:
            print('Time to Run Scripts: %s' % str(time.time()-st))

        if return_output: 
            return output


    def dir_exists(self, dir):
        output = self.run('[ -d "'+dir+'" ] && echo "True" || echo "False"', cmd=True, return_output=True)
        if 'True' in output: return True 
        else: return False
    

    def open_shell(self, port=22):
        '''Open an active shell. --Only works when run from the command prompt--'''
        methods.active_shell(self.instance, self.profile['username'], kp_dir=self.kp_dir)
    

    def terminate(self): 
        '''Terminate the instance'''
        methods.terminate_instance(self.instance['InstanceId'])                    