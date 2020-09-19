"""
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot-connect

Spotted module: 

The spotted class can implement all the functionality of connect.py but it can 
be run from a notebook or python script and it can be handled by other scripts.

MIT License 2020
"""

import sys, time, os, copy, boto3
from path import Path

root = Path(os.path.dirname(os.path.abspath(__file__)))

from spot_connect import sutils, ec2_methods, iam_methods, efs_methods, instance_methods, bash_scripts
from spot_connect.bash_scripts import update_git_repo

class SpotInstance: 
    
    profiles=None

    name            =   None 
    instance_id     =   None 
    key_pair        =   None 
    security_group  =   None
    instance_profile=   None 
    
    profile         =   None
    efs_mount       =   None 
    firewall        =   None 
    image_id        =   None 
    price           =   None 
    region          =   None 
    script          =   None 
    username        =   None
    
    filesystem     =   None
    new_mount       =   None 
    upload          =   None 
    remote_path     =   None 
    monitoring      =   None 
    
    client          =   None
    kp_dir          =   None 
    instance        =   None 
    mount_target    =   None 
    instance_dns    =   None 
    instance_type   =   None 
    filesystem_dns  =   None 
    filled_profile  =   None 
   
    def __init__(self,
                 name           :   str,
                 instance_id    :   bool  = False,
                 profile        :   str   = None, 
                 key_pair       :   str   = None, 
                 kp_dir         :   str   = None,
                 security_group :   str   = None, 
                 instance_profile : str   = '', 
                 efs_mount      :   bool  = False, 
                 firewall       :   tuple = None, 
                 image_id       :   str   = None, 
                 price          :   float = None, 
                 region         :   str   = None, 
                 scripts        :   list  = None, 
                 username       :   str   = None,
                 filesystem     :   str   = None,
                 new_mount      :   bool  = False, 
                 monitoring     :   bool  = False):
        '''
        A class to run, control and interact with spot instances. 
        __________
        parameters
        - name : str. name for spot instance launch group (will be used as identifier)
        - instance_id : bool. if True, consider instance id string (overrides --name)
        - profile : dict of settings for the spot instance
        - instance_profile : str. Instance profile with attached IAM roles
        - monitoring : bool, default True. set monitoring to True for the instance 
        - filesystem : string, default <name>. Filesystem to connect to the instance. If you want a new EFS to be created with this name set efs_mount = True, if an efs with the same name exists then the instance will be connected to it. 
        - image_id : Image ID from AWS. go to the launch-wizard to get the image IDs or use the boto3 client.describe_images() with Owners of Filters parameters to reduce wait time and find what you need.
        - instance_type : Get a list of instance types and prices at https://aws.amazon.com/ec2/spot/pricing/ 
        - price : float. maximum price willing to pay for the instance. 
        - region : string. AWS region
        - username : string. This will usually depend on the operating system of the image used. For a list of operating systems and defaul usernames check https://alestic.com/2014/01/ec2-ssh-username/
        - key_pair : string. name of the keypair to use. Will search for `key_pair`.pem in the current directory 
        - kp_dir : string. path name for where to store the key pair files 
        - sec_group : string. name of the security group to use
        - efs_mount : bool. (for advanced use) If True, attach EFS mount. If no EFS mount with the name <filesystem> exists one is created. If filesystem is None the new EFS will have the same name as the instance  
        - new_mount : bool. (for advanced use) If True, create a new mount target on the EFS, even if one exists. If False, will be set to True if file system is submitted but no mount target is detected.
        - firewall : str. Firewall settings
        '''

        self.profile = None 

        profiles=sutils.load_profiles()         

        if instance_id: 
            self.using_id = True 
        else: 
            self.using_id = False 

        self.name = name 
        self.client = None         

        if profile is None: 
            if not self.using_id:
                raise Exception('Must specify a profile')  
            else:
                self.profile = profiles[list(profiles.keys())[0]]
        else: 
            self.profile=copy.deepcopy(profiles[profile])        

        if key_pair is not None:
            self.profile['key_pair']=(key_pair, key_pair+'.pem')

        self.filesystem = None 

        if filesystem is None: 
            self.filesystem=''
            self.profile['efs_mount'] = False
            print('No EFS mount requested for this instance.')                                         
        else:
            self.filesystem=filesystem
            self.profile['efs_mount'] = True
            print('Instance will be mounted on the '+self.filesystem+' elastic filesystem')
        
        if firewall is not None:
            self.profile['firewall']=firewall
        
        if image_id is not None:
            self.profile['image_id']=image_id
        
        if price is not None:
            self.profile['price']=price
        
        if region is not None:
            self.profile['region']=region
        
        if username is not None:
            self.profile['username']=username
        
        if security_group is not None: 
            sg = iam_methods.retrieve_security_group(security_group, region=self.profile['region'])    
            self.profile['security_group'] = (sg['GroupId'], self.sec_group)          
            
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

        # Add a forward slash to the kp_dir 
        if self.kp_dir[-1]!='/': self.kp_dir = self.kp_dir + '/'

        self.new_mount = new_mount        
        self.monitoring = monitoring 
        self.instance_profile = instance_profile
               
        print('', flush=True)
        print('#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#', flush=True)
        print('#~#~#~#~#~#~#~# Spotting '+self.name, flush=True)
        print('#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#~#', flush=True)
        print('', flush=True)
        
        self.filled_profile = None         

        # Launch the Instance 
        # Launch the instance using the name profile, instance profile and monitoring arguments     
        try:         
            # If a key pair and security group were not added provided, they wil be created using the name of the instance                                
            self.instance, self.profile = ec2_methods.get_spot_instance(self.name, self.profile, instance_profile=self.instance_profile, monitoring=self.monitoring, kp_dir=self.kp_dir, using_instance_id=self.using_id)  # Launch or connect to the spot instance under the given name 
        except Exception as e:
            raise e
            sys.exit(1)
       
        # Mount Elastic File System
        if self.profile['efs_mount']: 
           
            print('Requesting EFS mount...')            
            fs_name = self.filesystem                 
            try:                                
                self.mount_target, self.instance_dns, self.filesystem_dns = efs_methods.retrieve_efs_mount(fs_name, self.instance, new_mount=self.new_mount, region=self.profile['region'])
            except Exception as e: 
                raise e 
                sys.exit(1)        
            print('Connecting instance to link EFS...')
            instance_methods.run_script(self.instance, self.profile['username'], bash_scripts.compose_mount_script(self.filesystem_dns), kp_dir=self.kp_dir, cmd=True)
        
        # Automatically Run Scripts 
        st = time.time()
        
        if scripts is not None: 
            for script in scripts: 
                print('\nExecuting script "%s"...' % str(script))
                try: 
                    if not instance_methods.run_script(self.instance, self.profile['username'], script, kp_dir=self.kp_dir):
                        break
                except Exception as e:
                    print(str(e))
                    print('Script %s failed with above error' % script)
                    
                print('Time to run script: %s' % str(time.time()-st))
                    
        self.state = self.instance['State']['Name']

        print('\nDone. Current instance state: '+self.state)
    
    
    def refresh_instance(self, verbose=True):
        '''Refresh the instance to get its current status & information'''

        client = boto3.client('ec2', region_name=self.profile['region'])

        reservations = client.describe_instances(InstanceIds=[self.instance['InstanceId']])['Reservations']
        self.instance = reservations[0]['Instances'][0]                             
        self.state = self.instance['State']['Name']
        if verbose: 
            print('Instance refreshed, current state: %s' % str(self.state))


    def upload(self, files, remotepath, verbose=False):
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
        instance_methods.upload_to_ec2(self.instance, self.profile['username'], files_to_upload, remote_dir=remotepath, kp_dir=self.kp_dir, verbose=verbose)    
    
        if verbose:
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
        instance_methods.download_from_ec2(self.instance, self.profile['username'], files_to_download, put=localpath, kp_dir=self.kp_dir)
    
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
                if return_output: run_stat, output = instance_methods.run_script(self.instance, self.profile['username'], script, cmd=cmd, kp_dir=self.kp_dir, return_output=return_output)
                else: run_stat = instance_methods.run_script(self.instance, self.profile['username'], script, cmd=cmd, kp_dir=self.kp_dir, return_output=return_output)

                if not run_stat:
                    break
            except Exception as e: 
                print(str(e))
                print('Script %s failed with above error' % script)
    
        if time_it:
            print('Time to Run Scripts: %s' % str(time.time()-st))

        if return_output: 
            return output


    def clone_repo(self, repo_link, directory='/home/ec2-user/efs/'):
        '''
		Clone a git repo to the instance. Must specify a directory and target folder on the instance. This is so that organization on the instance is actively tracked by the user. 
		Private Repos - the links for private repositories should be formatted as: https://username:password@github.com/username/repo_name.git
		__________
		parameters
		- repo_link : str. Git repo link. The command executed is: git clone <repo_link> <path>
		- directory : str. Instance directory to place the target folder and git repo. If directory is '.' target folder will be created in the home directory. To view the home directory for a given instance use the LinkAWS.get_instance_home_directory method
		'''
        proceed = self.dir_exists(directory)
        if proceed:				
            self.run('cd '+directory+'\ngit clone '+repo_link+'', cmd=True)
        else:
            raise Exception(str(directory)+' directory was not found on instance')


    def update_repo(self, path_on_instance, branch=None, repo_link=None):
        '''
		Update a given local repo to match the remote  
		__________
		parameters
		- path_on_instance : str. The path to the local repo folder in the instance 
		- branch : str. switch to this branch of the repo 
		- repo_link : str. Mainly for private repos. In order to git pull a private repo you must submit a link of the format https://username:password@github.com/username/repo_name.git 
		'''
        proceed = self.dir_exists(path_on_instance)
        if proceed:
            command = update_git_repo(path_on_instance, branch=branch, repo_link=repo_link, command='')
            self.run(command, cmd=True)
        else:
            raise Exception(str(path_on_instance)+' path was not found on instance')
               

    def dir_exists(self, directory):
        '''Check if a directory exists'''
        # This method is critical for the s3 sync to work in the instance manager 
        output = self.run('[ -d "'+directory+'" ] && echo "True" || echo "False"', cmd=True, return_output=True)
        if 'True' in output: return True 
        else: return False
        

    def terminate(self): 
        '''Terminate the instance'''
        instance_methods.terminate_instance(self.instance['InstanceId'])     


