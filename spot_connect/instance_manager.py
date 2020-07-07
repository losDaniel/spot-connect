'''
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot-connect

LinkAWS Class:

Class to quickly perform data syncronization and distributed tasks on AWS 
infrastructure using the spotted module. 

MIT License 2020
'''

import boto3, os, time
from path import Path 

root = Path(os.path.dirname(os.path.abspath(__file__)))

from spot_connect import sutils 
from spot_connect import spotted 
from spot_connect.sutils import genrs, load_profiles, split_workloads
from spot_connect.bash_scripts import compose_s3_sync_script
from spot_connect.fleet_methods import launch_spot_fleet, get_fleet_instances
from spot_connect.efs_methods import launch_efs
from spot_connect.ec2_methods import check_instance_initialization

from IPython.display import clear_output


# TODO : Add bash script to reduce spot fleet capacity. Or check that, if its going to reduce it to zero, to cancel it. 

class InstanceManager:
    
    efs = None 
    kp_dir = None 
    instances = None 
    fleets = None 
    
    def __init__(self, kp_dir=None, efs=None): 
        '''
        The InstanceManager class provides a number of shortcuts for managing ec2 instances. 
        These functions range from requesting instances on AWS to setting up distributed 
        workloads. 
        __________
        parameters
        - kp_dir : str. Key pair directory, if none is submitted default spot-connect directory will be used. 
                   If a default has not been set you will be prompted for one.
        - efs : str. Name of the default elastic file system you would like instances managed by this link 
                to connect to.
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
        
        self.instances = {}
        self.fleets = {} 

    def list_all_profiles(self):
        return load_profiles() 

    def launch_instance(self,
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
        Launch a spot instance and store it in the LinkAWS.instances dict attribute. 
        Default parameters are the same as for the spotted.SpotInstance Class. 
        For parameter descriptions use: help(spot_connect.spotted.SpotInstance)
        '''        
        if kp_dir is None:
            kp_dir = self.kp_dir
        if filesystem is None: 
            filesystem = self.efs
    
        instance = spotted.SpotInstance(name, 
                                        instance_id=instance_id,
                                        profile=profile,
                                        key_pair=key_pair,
                                        kp_dir=kp_dir,
                                        security_group=security_group,
                                        instance_profile=instance_profile,
                                        efs_mount=efs_mount,
                                        firewall=firewall,
                                        image_id=image_id,
                                        price=price,
                                        region=region,
                                        scripts=scripts,
                                        username=username,
                                        filesystem=filesystem,
                                        new_mount=new_mount,
                                        monitoring=monitoring)
        self.instances[name] = instance
        

    def show_instances(self): 
        '''Show the attached instances and their status'''
        display_dict = {} 

        for key in self.instances: 
            self.instances[key].refresh_instance(verbose=False)
            display_dict[key] = self.instances[key].instance['State']['Name']        

        print(display_dict)


    def quick_launch(self, instance_name='monitor', profile='t2.micro'):
        '''
        Will launch the cheapest possible instance with a unique name. 
        
        The instance can be used to submit commands directly. For example, to list the folders in a directory in the efs just submit: 
           self.instances[<name>].run('ls /efs/database/', cmd=True)
           
		You can connect your command prompt to the instance using $ spot_connect -n <instance_name> -a True
        __________
        parameters
        - instance_name : str. if the instance fails to connect submit a new name (check if any old keys are present in your awsdir)
        - profile : spot_connect.py profile you want to use. default is "default"
        '''
        iname = instance_name+'_'+genrs(length=3)
        print('Instance name is:', iname)
        self.instances[iname] = spotted.SpotInstance(iname, profile=profile, filesystem=self.efs, kp_dir=self.kp_dir)
        

    def terminate(self, instance_name):
        '''Terminate the given instance'''
        self.instances[instance_name].terminate()


    def create_elastic_file_system(self, system_name, region):
        '''Create an elastic file system with the given system name in the given region. If the file system already exists that one will be returned'''        
        file_system = launch_efs(system_name, region=region)
        return file_system


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
                answer = ('You have not specified an EFS, the instance will shut down after the sync and your data may not persist. Do you want to continue (Y)? ')
                if answer == "Y":
                    fs = None
                else:
                    raise Exception('No EFS selected, user exit.')
            else:
                fs = self.efs 
        else:
            fs = efs
            
        didx = genrs(length=3)
        if instance_name is None: 
            iname = 'downloader_'+didx
        else: 
            iname = instance_name
            
        self.instances[iname] = spotted.SpotInstance(iname, profile='t3.small', filesystem=fs, kp_dir=self.kp_dir, instance_profile=instance_profile)
        
        # Check whether the s3 bucket is the source or destination 
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
            command = compose_s3_sync_script(source, dest, instance_path, logfile=iname)

        self.instances[iname].run(command, cmd=True)

        print('Files and directories from '+source+' are being is being synced to '+dest+' on the instance "'+iname+'"') 
        print('The instance will be shutdown and terminated when the job is complete.')
        print('Use the following to check progress: SpotInstance("'+iname+'").run("cat '+instance_path+'/'+iname+'.txt", cmd=True)')        
        
        
    def split_workload(self, n_jobs, workload, wrkdir=None, filename=None): 
        '''Split a list into n_job chunks and save each chunk, return the list of filenames'''        
        return split_workloads(n_jobs, workload, wrkdir=None, filename=None)         
        
    
    def launch_fleet(self,
                     account_number,
                     n_instances, 
                     profile, 
                     name=None, 
                     instance_profile='',
                     monitoring=True,
                     kp_dir=None, 
                     enable_nfs=True,
                     enable_ds=True):
        '''
        Launch a spot fleet and store it in the LinkAWS.fleets dict attribute. 
        Each item has as the key a fleet id and as the value a dictionary the key 'instances' with its respective instances and the key 'name' if a name was submitted. 
        Use the refresh_fleet_instances command to update the instances in each fleet 

        For parameter descriptions use: help(spot_connect.fleet_methods.launch_spot_fleet)
        The attribute ['instances'] key in each fleet is a response from describe_spot_fleet_instances of the format: 
           
            [{'InstanceId': 'i-07bcc7d2aq23
              'InstanceType': 't3.micro',
              'SpotInstanceRequestId': 'sir-ad32k5j',
              'InstanceHealth': 'healthy'},
             {'InstanceId': 'i-0dbec856841',
              'InstanceType': 't3.micro',
              'SpotInstanceRequestId': 'sir-848rwg',
              'InstanceHealth': 'healthy'}]
        '''
        profiles=sutils.load_profiles()         
        profile = profiles[profile]

        # Submit a request to launch a spot fleet with the given number of instances 
        response = launch_spot_fleet(account_number, 
                                     n_instances=n_instances,
                                     profile=profile, 
                                     name=name, 
                                     instance_profile=instance_profile,
                                     monitoring=monitoring,
                                     kp_dir=kp_dir,
                                     enable_nfs=enable_nfs,
                                     enable_ds=enable_ds)        
        # Get the request id for the fleet 
        spot_fleet_req_id = response['SpotFleetRequestId']

        # Get a list of the instances associated with the fleet 
        fleet_instances = get_fleet_instances(spot_fleet_req_id, region=profile['region'])

        # Assign the fleet and its instances to the self.fleets attribute
        self.fleets[spot_fleet_req_id] = {}        
        self.fleets[spot_fleet_req_id]['instances'] = fleet_instances['ActiveInstances']
        self.fleets[spot_fleet_req_id]['region'] = profile['region']
        if name is not None: 
            self.fleets[spot_fleet_req_id]['name'] = name
    
        return spot_fleet_req_id
        
    def refresh_fleet_instances(self, fleet_id=None):
        '''Refresh the list of instances for a given fleet. If no fleet is submitted refresh all in self.fleets'''
        if fleet_id is not None: 
            self.fleets[fleet_id]['instances'] = get_fleet_instances(fleet_id, self.fleets[fleet_id]['region'])
        for fleet in self.fleets: 
            self.fleets[fleet]['instances'] = get_fleet_instances(fleet, self.fleets[fleet]['region'])


    def _distribute_jobs_on_fleet(self, spot_fleet_req_id, profile, scripts, uploads=None):
        '''Assign instances in a fleet to execute specific scripts'''                
        # Get the number of active instances 
        num_active_instances = len(self.fleets[spot_fleet_req_id]['instances'])
        
        # Wait until the instnaces start activating
        while num_active_instances == 0: 
            time.sleep(5)
            self.refresh_fleet_instances(fleet_id=spot_fleet_req_id)
            num_active_instances = len(self.fleets[spot_fleet_req_id]['instances'])
        
        distributed_jobs = {} 
        distributed_jobs['assigned_fleet'] = spot_fleet_req_id
        
        # Job assignments to fleet instances are organized by script
        for num, script in enumerate(scripts):
            distributed_jobs[num] = {} 
            distributed_jobs[num]['status'] = 'empty'
            distributed_jobs[num]['script'] = script 
            if uploads is not None: 
                distributed_jobs[num]['upload'] = uploads[num]

        empty_jobs = [j for j in distributed_jobs if distributed_jobs[j]['status']=='empty']
        
        # Get each instance from the spot fleet 
        for inum, instance in enumerate(self.fleets[spot_fleet_req_id]['instances']):

            instance_id = instance['InstanceId']
            
            # If the instance has not been assigned 
            if 'assigned' not in instance: 
                # Assign it an empty job
                job = empty_jobs[0]

                # Get the first available job 
                distributed_jobs[job]['instance'] = instance_id        # Assign it the current instance 
                
                # Wait for the instance to be initialized                        
                instance_status = check_instance_initialization(instance_id, region=profile['region'])
                
                distributed_jobs[job]['status'] = instance_status
                
                self.instances[instance_id] = self.launch_instance(instance_id, instance_id=instance_id, profile=profile)
                
                # Once it has been initialized upload the script and make the 
                if uploads is not None: 
                    self.instances[instance_id].upload(distributed_jobs[job]['upload'])
                self.instances[instance_id].run(distributed_jobs[job]['script'], cmd=True)
                    
                print('Job %s Launched' % str(job))                
                empty_jobs.pop(0)
                
                self.fleets[spot_fleet_req_id]['instances'][inum]['assigned'] = True                

        return distributed_jobs
    
    
    def monitor_distributed_jobs(self, distributed_jobs):
        '''Monitor a set of distributed jobs, if any instance should be shut-down and changed, relaunch the corresponding script'''
        # Distributed jobs dictionary has indices as keys. 
        # Each index has its script and an assigned index. 
        
        spot_fleet_req_id = distributed_jobs['assigned_fleet']
        
        # monitor the instances for this spot fleet. 
        
        # if the list changes
        # find the one that has been removed in the distributed jobs 
        # replace that instance with a connection to the new one. 
        pass
        

    
    def run_distributed_jobs(self, prefix, n_jobs, scripts, profile, instance_profile='', filesystem=None, uploads=None, upload_path='.', use_fleet=False, account_number=None):
        '''
        Distribute scripts and workloads across a given number of instances with a given profile
        __________
        parameters
        - prefix : str. Name given to each instance of fleet 
        - n_jobs : int. Number of different instances to launch (if use_fleet=True, fleet will request this number of instances).
        - scripts : list. List of scripts formatted as strings (not filenames, the actual bash scripts with new line delimiters), note len(scripts) == n_jobs
        - profile : str. The name of the profile to use for the instances.
        - filesystem : str. The CreateionToken for the filesystem you want to connect to each instance.
        - uploads : list. List of filepaths to files you want to upload to each instance, note len(uploads) == n_jobs
        - upload_path : str. The path on each instance to upload the corresponding file to.
        - use_fleet : bool. If true, returns distributed_jobs dictionary. Use spot fleet. If spot fleets are used, if an instance is interrupted it will automatically 
        - account_number : str. If use_fleet == True, this is needed to request a fleet. 
        '''
        
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
                
        if use_fleet: 
            # Launch the spot fleet 
            spot_fleet_req_id = self.launch_fleet(account_number, n_jobs, profile, name=prefix, instance_profile=instance_profile, monitoring=True, kp_dir=self.kp_dir)

            # Assign the scripts to different instances 
            distributed_jobs = self._distribute_jobs_on_fleet(spot_fleet_req_id, profile, scripts, uploads=uploads)            
            return distributed_jobs

        else: 
            # If spot fleet is not enabled launch each instance separately. This takes considerably more time. 
            for nn in range(n_jobs):                 
                self.launch_instance(prefix+'_'+str(nn), profile=profile, filesystem=fs, instance_profile=instance_profile, efs_mount=None, new_mount=None)
    
                if uploads is not None: 
                    self.instances[prefix+'_'+str(nn)].upload(uploads[nn], upload_path)
    
                self.instances[prefix+'_'+str(nn)].run(scripts[nn], cmd=True)            		
                
                clear_output(wait=True)
                print('Job %s Launched' % str(nn))