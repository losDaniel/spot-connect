'''
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot-connect

LinkAWS Class:

Class to quickly perform data syncronization and distributed tasks on AWS 
infrastructure using the spotted module. 

MIT License 2020
'''

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

    def transfer_efs_s3(self, source, dest, efs=None, instance_profile=None):

    	if efs is None: 
    		if self.efs is None: 
    			raise Exception('Must select an elastic file system name, if the name does not match an existing EFS one will be created')
    		else: 
    			fs = self.efs 
    	else: 
    		fs = efs

    	self.downloader = spotted.SpotInstance('downloader_'+genrs(), profile='t3.small', filesystem=fs, kp_dir=self.kp_dir)



    def syncDatabaseWithEfs(self, efs_path='/home/ec2-user/efs/database/', bucket_name='day-trader', instance_profile='ec2_s3', instance_name='efs_downloader'):
        '''
        Create an instance to download the database to the EFS. 
        The instance will terminate automatically when the job is done
        Check on the status using the monitor: self.monitor.run('cat efs/database/download.txt', cmd=True)
        __________
        parameters
        - efs_path : str. the directory in the EFS where you want to replicate the S3 structure 
        - bucket_name : str. name of the s3 bucket to download to the efs 
        - instance_profile : str. instance profile to grant the ec2 a role that can access S3
        - instance_name : str. if the instance fails to connect submit a new name (check if any old keys are present in your awsdir)
        '''
        bucket_name = bucket_name.lower()
        instance = spotted.spotted(instance_name, profile='t3.small', filesystem=self.efs, kp_dir=self.kp_dir)

        # Compose the AWS s3 sync command which consists of three separate commands
        # 1) The aws s3 sync command in background and route the output to download.txt 2) save the job number in curpid 3) when the job is done shutdown the instance        
        command = "nohup aws s3 sync s3://"+bucket_name+" "+efs_path+" &> download.txt &\ncurpid=$!\nnohup sh -c 'while ps -p $0 &> /dev/null; do sleep 10 ; done && sudo shutdown -h now ' $curpid &> run.txt &"
        print('Instance is running command %s' % command)
        instance.run(command, cmd=True)
        
    def check_downloadDatabaseToEFS(self, efs_path='/home/ec2-user/efs/database/'):
        self.monitor.run(efs_path + '/download.txt', cmd=True)

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

