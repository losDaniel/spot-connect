'''
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot-connect

LinkAWS Class:

Class to quickly perform data syncronization and distributed tasks on AWS 
infrastructure using the spotted module. 

MIT License 2020
'''

import boto3 

from IPython.display import clear_output
from spot_connect.sutils import genrs
from spot_connect.spotted import SpotInstance

class LinkAWS:
    
    efs = None 
    kp_dir = None 
    monitor = None 
    
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
        
    def terminate_monitor(self):
    	'''Terminate the monitor instance'''
        self.monitor.terminate()

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

    def instance_s3_transfer(self, source, dest, efs=None, instance_profile=None):
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
		self.downloader = spotted.SpotInstance('downloader_'+didx, profile='t3.small', filesystem=fs, kp_dir=self.kp_dir)

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
	        command +='nohup aws s3 sync '+source+' '+dest+' &> download_'+didx+'.txt &\n'
	        # Get the job id for the last command
	        command +='curpid=$!\n'
	        # When the job with the given job id finishes, shut down and terminate the instance  
	        command +="nohup sh -c 'while ps -p $0 &> /dev/null; do sleep 10 ; done && sudo shutdown -h now ' $curpid &> run.txt &\n"

        self.downloader.run(command, cmd=True)

        print('Files and directories from '+source+' are being is being synced to '+dest+' on the instance downloader_'+didx) 
        print('The instance will be shutdown and terminated when the job is complete.')
		print('Use the following to check progress: <SpotInstance("downloader_'+didx+'")>.run("'+instance_path+'/download_'+didx+'.txt", cmd=True)')
        

	def clone_repo(self, instance, repo_link, target_folder, directory='/home/ec2-user/efs/'):
		'''
		Clone a git repo to the instance. Must specify a directory and target folder on the instance. This is so that organization on the instance is actively tracked by the user. 

		Private Repos - the links for private repositories should be formatted as: https://username:password@github.com/username/repo_name.git
		__________
		parameters
		- instance : spotted.SpotInstance. The specific instance in which to clone the repo 
		- repo_link : str. Git repo link. The command executed is: git clone <repo_link> <path>
		- target_folder : str. Name of the folder to store the repo in, folder will be created in the given directory
		- directory : str. Instance directory to place the target folder and git repo. If directory is '.' target folder will be created in the home directory. To view the home directory for a given instance use the LinkAWS.get_instance_home_directory method
		'''
		proceed = instance.dir_exists(directory)
		if proceed:				
			instance.run('git clone '+repo_link+'', cmd=True)
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
		proceed = instance.dir_exists(directory)
		if proceed:				

	        command = ''
	        command +='cd '+directory+'\n'
	        command +='git checkout '+branch+'\n'
	        if repo_link is None: 
	        	command+='git pull origin/'+branch+'\n'
	        else: 
	        	command+='git pull '+repo_link+'\n'
		else: 
			raise Exception(str(directory)+' path was not found on instance')

	def run_distributed_jobs(self):

		spot_fleet = {} 

		for nn in jobs: 
			
			clear_output(wait=True)


    def runDistributedAprJobs(self, prefix, jobs, upload_path, use_profile='c5.large'):
        '''Distribute the APR Jobs across a series of instances with the given profile'''

        # Instantiate a dictionary to track all the instances currently executing remote jobs 
        spot_fleet = {} 

        for nn in jobs:

            clear_output(wait=True)
            
            # Modify the apr template to run the apr recognition onthe given template 
            self.set_distributed_apr(nn)

            # Create an instance for the current permutation and add it to the fleet 
            spot_fleet[nn] = spotted.spotted(prefix+nn, profile=use_profile, filesystem=self.efs, kp_dir=self.kp_dir)

            # Upload the files we will need on the instance
            spot_fleet[nn].upload(upload_path+'/'+nn+'.pickle', '/home/ec2-user/efs/Day-Trader/data/outline_permutations')

            # This runs a LOCAL file (aws/set_apr.sh). It loads it and then submits each command to the linux instance remotely 
            spot_fleet[nn].run('aws/set_apr.sh')
            
        return spot_fleet    



    def set_distributed_apr(self, nickname, strategy='ABCDH', database='/home/ec2-user/efs/database/', resultpath='/home/ec2-user/efs/ABCDH/', overwrite='False'):
        '''Modify the set_apr.sh script to accomodate whatever variables we need'''
        
        with open(self.awsdir+'/set_apr_template.sh', 'r') as f: 
            txt = f.read()
            txt = txt.replace('STRATEGYNAME',strategy)
            txt = txt.replace('DATABASE',database)
            txt = txt.replace('RESULTPATH',resultpath)
            # The findPatterns method in strategy miner will create a PERMNICKNAME folder in the RESULTPATH
            txt = txt.replace('PERMNICKNAME', nickname)
            txt = txt.replace('OVERWRITEOPT', overwrite)
            txt = txt.replace('OUTPUT', 'Log_'+nickname+'.txt')
    
        with open(self.awsdir+'/set_apr.sh', 'w') as w: 
            w.write(txt)
            w.close()
          


    # DEPRECATED - run_s3_upload has been removed in favor of awscli methods which can be run through bash scripts
#    def uploadDatabaseToS3(self, bucket='day-trader', database='D:/Day-Trader/database', overwrite=False): 
#        '''Upload the database in the local path the given S3 bucket'''
#        bucket = bucket.lower()
#        run_s3_upload.upload_to_s3(bucket, database, overwrite)
        
    # DEPRECATED - run_s3_upload has been removed in favor of awscli methods which can be run through bash scripts
#    def downloadDatabaseToEFS(self, efs_path='/home/ec2-user/efs/database', bucket_name='day-trader', overwrite=False, instance_name='efs_downloader'):
#        '''
#        Create an instance to download the database to the EFS. 
#        The instance will terminate automatically when the job is done
#        Check on the status using the monitor: self.monitor.run('cat efs/database/download.txt', cmd=True)
#        __________
#        parameters
#        - efs_path : str. the directory in the EFS where you want to replicate the S3 structure 
#        - instance_name : str. if the instance fails to connect submit a new name (check if any old keys are present in your awsdir)
#        - instance_profile : str. instance profile to grant the ec2 a role that can access S3
#        '''
#        bucket_name = bucket_name.lower()
#        instance = spotted.spotted(instance_name, profile='t3.small', filesystem=self.efs, kp_dir=self.kp_dir)
#        
#        # Upload the script that we want in the EFS directory where the S3 file structure will be immitated
#        instance.upload(self.awsdir+'/run_s3_download.py', efs_path)
#        
#        txt = open(self.awsdir+'/s3_efs_transfer.sh', 'r').read()
#        self.substitute_in_bash_script('DIRECTORY', efs_path, self.awsdir+'/s3_efs_transfer.sh')
#        self.substitute_in_bash_script('BUCKETNAME', bucket_name, self.awsdir+'/s3_efs_transfer.sh')
#        self.substitute_in_bash_script('OVERWRITE', str(overwrite), self.awsdir+'/s3_efs_transfer.sh')
#                
#        # Run the commands in this LOCAL file to download all the S3 files onto the EFS 
#        instance.run(self.awsdir+'/s3_efs_transfer.sh')
#        
#        with open(self.awsdir+'/s3_efs_transfer.sh', 'w') as f:
#            f.write(txt)
#            f.close()
            
    ### DEPRECATED - Its exponentially faster to use AWS CLI functions such as >> aws sycn s3 s3://day-trader local_file
#    def downloadFromS3(self, bucket='day-trader', database='D:/Day-Trader/database', overwrite=False):
#        '''Download the Strategy data from the S3 bucket to the local path'''
#        bucket = bucket.lower()
#        wd = os.getcwd()
#        os.chdir(database)
#        run_s3_download.s3_download(bucket, overwrite)
#        os.chdir(wd)

