# -*- coding: utf-8 -*-
"""
Upload data to S3 + Setup and Run AWS DataSync between specified S3 and EFS locations. 

AWS datasync is a process specialized in transfering data. There are 4 components to a datasync: 
- Agent: A virtual machine used to read data from or write data.
- Location: Any source or destination location used in the data transfer (for example, Amazon S3 or Amazon EFS).
- Task: A task includes two locations, and also the configuration of how to transfer the data. A task is the complete definition of a data transfer.
- Task execution: An individual run of a task, which includes options such as start time, end time, bytes written, and status.

There are 5 tasks to the datasync: 
- Step 1: Create an Agent
- Step 2: Create Locations
- Step 3: Create a Task
- Step 4: Start a Task Execution
- Step 5: Monitor Your Task Execution

For detailed documentation see https://docs.aws.amazon.com/datasync/latest/userguide/using-cli.html

Notes: 
  <create an agent> You can use "python spot_connect.py -n test -p datasync" to create a spot instance that can be used to activate an agent. 
                    The agent can be an ec2 instance with a special datasync image AMI provided by AWS. Each datasync image is specific to its region. 
                    For a list of regional-images see: https://docs.aws.amazon.com/datasync/latest/userguide/deploy-agents.html#ec2-deploy-agent
                    Launching an ec2 instance also requires picking an instance type. 
                    For recommended instance types see: https://docs.aws.amazon.com/datasync/latest/userguide/requirements.html#ec2-instance-types
  
  <EFS location> The efs location and mount target can be created using spot_connect.py when creating a stand-alone spot instance if no pre-existing EFS is specified.  

  <uploading> AWS Does not recommend transfering directly from a local source to EFS so first we upload our data to S3 which is pretty cheap. 
  
  <roles> Make sure you have an admin role available for the datasync, otherwise your datasync will fail due to permissions
  
  <configuration> the aws client has already been configured using the awscli through the anaconda prompt

**Imports: Script will install non-native requirements automatically 
"""

try:
    import boto3
except:
    import pip
    pip.main(['install', 'boto3'])    
    import boto3
import os, sys, argparse

def absolute_file_paths(directory):
    '''Returns a list with the full file paths for every file in the given directory'''
    for dirpath,_,filenames in os.walk(directory):
        for f in filenames:
            yield os.path.abspath(os.path.join(dirpath, f))



def populate_S3(bucket_name, region, files_to_upload):
    '''
    Upload files to the given bucket in the given region. If bucket does not exist, create it
    __________
    parameters
    - bucket_name : string. Name of S3 bucket
    - region : string. AWS region
    - files_to_upload : list of local files to upload to S3 
    '''
    # show all the buckets in the s3 resource
    s3r = boto3.resource('s3')
    if bucket_name not in list(s3r.buckets.all()): 
        s3r.create_bucket(Bucket=bucket_name, 
                          CreateBucketConfiguration={
                             'LocationConstraint':region 
                          })
    # upload local files to s3
    s3 = boto3.client('s3')
    
    progress = 0 
    for file in files_to_upload: 
        s3.upload_file(file, bucket_name, file.split('\\')[-1])
        progress += 1
        print('Uploading %.0f%% Complete' % float(100*(progress/len(files_to_upload))))



if __name__ == '__main__':   
    
    parser = argparse.ArgumentParser(description='Setup Datasync')
    parser.add_argument('-n', '--name', help='Name of the S3 bucket', required=True)
    parser.add_argument('-d', '--directory', help='Name of local directory with files to upload', required=True)
    parser.add_argument('-r', '--region', help='AWS region', default='us-west-2')
    args = parser.parse_args()
    
    try: 
        populate_S3(args.name, args.region, args.directory)
    except Exception as e: 
        raise e 
        sys.exit(1)    