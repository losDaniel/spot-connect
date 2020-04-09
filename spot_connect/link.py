'''
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot-connect

LinkAWS Class:

Class to quickly perform data syncronization and distributed tasks on AWS 
infrastructure using the spotted module. 

MIT License 2020
'''

import boto3, os
from path import Path 

root = Path(os.path.dirname(os.path.abspath(__file__)))

from spot_connect import sutils 
from spot_connect import spotted 
from spot_connect.sutils import genrs, load_profiles

from IPython.display import clear_output

class LinkAWS:
    
    efs = None 
    kp_dir = None 
    monitor = None 
    instances = None 
    
    def __init__(self, kp_dir=None, efs=None): 
        '''
        
        __________
        parameters
        - kp_dir : str. Key pair directory, if none is submitted default spot-connect directory will be used. If a default has not been set you will be prompted for one.
        - efs : str. Name of the default elastic file system you would like instances managed by this link to connect to.
        '''

        self.kp_dir = None 
        if kp_dir is None: 
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
        else: 
	        self.kp_dir = kp_dir

        if efs is None: 
        	self.efs = None 
        else: 
        	self.efs = efs 

        self.monitor = None   
        self.downloader = None           
        
        self.instances = {} 

    def list_profiles(self):
        return load_profiles() 

    def launch_instance(self, 
                        name, 
                        profile=None, 
                        filesystem=None,
                        kp_dir=None, 
                        monitoring=None, 
                        efs_mount=None,
                        new_mount=None, 
                        instance_profile=None
                        ): 
        '''        
        Launch a spot instance and store it in the LinkAWS.instances dict attribute. 
        Default parameters are the same as for the spotted.SpotInstance Class. 
        __________
        parameters
        - name : string. name of the spot instance
        - profile : dict of settings for the spot instance
        - filesystem : string, default <name>. creation token for the EFS you want to connect to the instance  
        - kp_dir : string. path name for where to store the key pair files 
        - monitoring : bool, default True. set monitoring to True for the instance 
        - efs_mount : bool. If True, attach EFS mount. If no EFS mount with the name <filesystem> exists one is created. If filesystem is None the new EFS will have the same name as the instance  
        - newmount : bool. If True, create a new mount target on the EFS, even if one exists
        - instance_profile : str. Instance profile with attached IAM roles
        '''
        
        if kp_dir is None:
            kp_dir = self.kp_dir
        if filesystem is None: 
            filesystem = self.efs
    
        instance = spotted.SpotInstance(name, 
                                        profile=profile, 
                                        filesystem=filesystem,
                                        kp_dir=kp_dir,
                                        monitoring=monitoring,
                                        efs_mount=efs_mount,
                                        newmount=new_mount,
                                        instance_profile=instance_profile,
                                        )
        self.instances[name] = instance

    def launch_monitor(self, instance_name='monitor', profile='default'):
        '''
        Will launch the cheapest possible instance to use as a monitor. 
        
        The instance can be used to submit commands directly. For example, to list the folders in a directory in the efs just submit: 
           self.monitor.run('ls /efs/database/', cmd=True)
           
		You can connect your command prompt to the instance using $ spot_connect -n <instance_name> -a True
        __________
        parameters
        - instance_name : str. if the instance fails to connect submit a new name (check if any old keys are present in your awsdir)
        - profile : spot_connect.py profile you want to use. default is "default"
        '''
        self.monitor = spotted.SpotInstance(instance_name+'_'+genrs(), profile=profile, filesystem=self.efs, kp_dir=self.kp_dir)
        self.instances['monitor'] = self.monitor 

    def terminate_monitor(self):
        '''Terminate the monitor instance'''
        self.monitor.terminate()


    def count_cores(self, instance):
        instance.upload(os.path.abspath(root)+'\\core_count.py', '.')
        cores = instance.run('python core_count.py', cmd=True, return_output=True)
        return cores


    def get_instance_home_directory(self, instance=None):
    	'''
    	Return the home directory for an instance
		__________
		parameters
		- instance : spotted.SpotInstance object. if None will use self.monitor 
    	'''
    	if instance is None: 
    		if self.monitor is None: 
    			raise Exception('No Instance. Use self.launch_monitor() or submit an instance')
    		else: 
    			itc = self.monitor 
    	else: 
    		itc = instance

    	output = itc.run('pwd', cmd=True, return_output=True)
    	return output 

    def instance_s3_transfer(self, source, dest, instance_profile, efs=None, instance_name=None):
        '''
    	Will launch a new instance to transfer files from an S3 bucket to an instance or vice-versa. 
    	The instance folder must include the home directory path such as "/home/ec2-user/<path>". 
    	If you do not know the home directory path for an instance use the link.LinkAWS.get_instance_home_directory() method.
		The bucket must be of the format "s3://<bucket_name>"
		__________
		parameters
		- source : str. path to an instance folder (usually starts with "/home/ec2-user/") or bucket of the form s3://<bucket name>
		- dest : str. path to an instance folder (usually starts with "/home/ec2-user/") or bucket of the form s3://<bucket name>
		- efs : str. Name for the elastic file system to mount on the instance, if None will attempt to use default, if none has been set will prompt the user for continue. 
		- instance_profile : str. instance profile to use for the instance, this is necessary to grant the instance access to S3. If None, default will be used. 
        '''
        
        if efs is None:
            if self.efs is None:
                answer = ('You have not specified an EFS, if either your source or destination are in your efs this will return an error. Do you want to continue? (Y/N)')
                if answer == "Y":
                    fs = None
                else:
                    raise Exception('No EFS selected, user exit.')
            else:
                fs = self.efs 
        else:
            fs = efs
            
        didx = genrs()

        if instance_name is None: 
            iname = 'downloader_'+didx
        else: 
            iname = instance_name
            
        self.downloader = spotted.SpotInstance(iname, profile='t3.small', filesystem=fs, kp_dir=self.kp_dir, instance_profile=instance_profile)
        
        if 's3://' in source: 
            instance_file_exists, instance_path, bucket_path = self.downloader.dir_exists(dest), dest, source 
        elif 's3://' in dest:
            instance_file_exists, instance_path, bucket_path = self.downloader.dir_exists(source), source, dest
        else:
            raise Exception('Either the source or dest must be an S3 bucket formatted as "s3://<bucket name>"')

    	# First check if the instance path exists in the instance then check if the bucket exists in S3 
        if not instance_file_exists:
            raise Exception(instance_path+' does not exist on the instance')
        else: 
            s3 = boto3.resource('s3')
            bucket_path_exists = s3.Bucket(bucket_path.replace('s3://','')) in s3.buckets.all()
        if not bucket_path_exists:
            raise Exception(bucket_path+' was not found in S3')
		# If both the bucket and instance path are OK we begin the sync 
        else: 
	        command = ''
	        # Run the aws s3 sync command in the background and send the output to download_<didx>.txt
	        command +='nohup aws s3 sync '+source+' '+dest+' &> '+instance_path+'/'+iname+'.txt &\n'
	        # Get the job id for the last command
	        command +='curpid=$!\n'
	        # When the job with the given job id finishes, shut down and terminate the instance  
	        command +="nohup sh -c 'while ps -p $0 &> /dev/null; do sleep 10 ; done && sudo shutdown -h now ' $curpid &> s3_transfer.txt &\n"

        self.downloader.run(command, cmd=True)

        print('Files and directories from '+source+' are being is being synced to '+dest+' on the instance "'+iname+'"') 
        print('The instance will be shutdown and terminated when the job is complete.')
        print('Use the following to check progress: SpotInstance("'+iname+'").run("cat '+instance_path+'/'+iname+'.txt", cmd=True)')
        

    def clone_repo(self, instance, repo_link, directory='/home/ec2-user/efs/'):
        '''
		Clone a git repo to the instance. Must specify a directory and target folder on the instance. This is so that organization on the instance is actively tracked by the user. 

		Private Repos - the links for private repositories should be formatted as: https://username:password@github.com/username/repo_name.git
		__________
		parameters
		- instance : spotted.SpotInstance. The specific instance in which to clone the repo 
		- repo_link : str. Git repo link. The command executed is: git clone <repo_link> <path>
		- directory : str. Instance directory to place the target folder and git repo. If directory is '.' target folder will be created in the home directory. To view the home directory for a given instance use the LinkAWS.get_instance_home_directory method
		'''
        proceed = instance.dir_exists(directory)
        if proceed:				
            instance.run('cd '+directory+'\ngit clone '+repo_link+'', cmd=True)
        else:
            raise Exception(str(directory)+' directory was not found on instance')
            
    
    def update_repo(self, instance, instance_path, branch='master', repo_link=None):
        '''
		Update a given local repo to match the remote  
		__________
		parameters
		- instance : spotted.SpotInstance. The specific instance to use 
		- instance_path : str. The path to the local repo folder in the instance 
		- branch : str. switch to this branch of the repo 
		- repo_link : str. Mainly for private repos. In order to git pull a private repo you must submit a link of the format https://username:password@github.com/username/repo_name.git 
		'''
        proceed = instance.dir_exists(instance_path)
        if proceed:
            command = ''
            command +='cd '+instance_path+'\n'
            command +='git checkout '+branch+'\n'
            if repo_link is None:
                command+='git pull origin '+branch+'\n'
            else:
                command+='git pull '+repo_link+'\n'
            instance.run(command, cmd=True)
        else:
            raise Exception(str(instance_path)+' path was not found on instance')
            
    def run_distributed_jobs(self, prefix, n_jobs, scripts, profile, filesystem=None, uploads=None, upload_path='.'):
        '''Distribute scripts and workloads across a given number of instances with a given profile'''
        
        if filesystem is not None: 
            fs = filesystem
        else: 
            fs = self.efs

        try: 
            assert len(scripts) == n_jobs
        except: 
            raise Exception('The number of scripts must be equal to the number of instances')

        if uploads is not None: 
            try:
                assert len(uploads)==n_jobs
            except: 
                raise Exception('If uploading material to each instance, must provide an equal number of materials and instances')
                
        for nn in range(n_jobs): 

            self.launch_instance(prefix+'_'+str(nn), profile=profile, filesystem=fs)

            if uploads is not None: 
                self.instances[prefix+'_'+str(nn)].upload(uploads[nn], upload_path)

            self.instances[prefix+'_'+str(nn)].run(scripts[nn], cmd=True)            		
            
            clear_output(wait=True)