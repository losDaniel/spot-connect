# Spot Instance AWS

This repository hosts a module to make launching and executing python scripts on AWS cheap and easy. Spot instances are excess capacity that AWS rents out at a discount through a bidding mechanism. Users can set a maximum price to bid on any excess capacity of any type of hardware loaded with any type of instance. Because spot instances rely on excess capacity they can be requisitioned by Amazon when demand increases, this gives users a 2 minute window to close their session and abandon the spot instance, forcing any unfinished work to resume on another spot instance should that be the user's choice. This module provides users the ability to: 

1) Easily launch a spot instance with any capacity and image they like

2) Easily upload or transfer small or large data amounts on and off their instances 

3) Monitor the requisition status of their spot-instance, save work and resume work on a new spot-instance 
<br><br>
## Spot Connect 

The `spot_connect.py` script can be executed from the command line to launch an instance or reconnect to an instance, mount an elastic files system, upload files, execute scripts and leave an active shell connected to the instance open in your command line. 

To launch an instance open your command prompt and use the following commands 


`cd <spot_connect.py directory>` 

`ptyhon spot_connect.py -n <name> -p <profile> -s <scripts> -f <filesystem> -u <files or dir to upload> -r <path on instance> -a <active shell>`

![LaunchInstance](https://github.com/dankUndertone/Spot-Instance-AWS/blob/master/launch_instance.gif)

The command above creates an instance called "test" and since no filesystem name is specified it creates an efs by the same name. It mounts the efs to the instance automatically and uploads one analysis script and one data file, then it runs the test script and leave an open shell for the user once everything is done.

### Options

`-n` <br>
*Name* for the spot instance, a key and security group will be created for the instance with this name. The private key will be saved to the directory in a .pem file. 

`-p` <br>
*Profile* dictionary of parameters that describe the instance to be launched. A set of pre-defined profiles are available in `spot_connect.py` that serve different purposes. See the **Profile Types** section below for a list of pre-set profiles. The dictionary keys that need to be filled are: 
* **firewall_ingress** - (protocol, ingress port, egress port, source IP group)
* **image_id** - Image ID (ami-) from AWS. Find available images using AWS instance launch-wizard or boto3.client('ec2').describe_images()
* **instance_type** - Get a list of instance types and descriptions at https://aws.amazon.com/ec2/instance-types/
* **price** - Maximum bidding price for an instance type. Get a list of prices at https://aws.amazon.com/ec2/spot/pricing/
* **region** - AWS region 
* **scripts** - List of scripts to be executed. This list is separate and executed before the scripts submitted when invoked through the command prompt. 
* **username** - Username to log into the instance. Depends on the instance AMI. For a list of default usernames see: https://alestic.com/2014/01/ec2-ssh-username/
* **efs_mount** - `True` or `False`. If true will check for an EFS mount in the instance and if one is not found it will create a file system or use an existing one with `-n` as the creation token and create a mount target and create a bash script `efs_mount.sh` in the local directory which can be executed within the instance to mount the EFS on the instance (in this repo `efs_mount_example.sh` is provided to avoid divulging any address in my cloud).

`-s` <br>
*Script* path or list of paths to scripts to be executed. 

`-f` <br>
*Filesystem* creation token name for file system that you want to use. If `-f` option is not set and `efs_mount == True` in the `-p` (profile) option then the `-n` (name) is used to identify or create the elastic file system. 

`-u` <br>
*Upload* is the file path or directory that will be uploaded via paramiko ssh transfer. Files or folders are assumed to be in the current directory. Upload speed appears to depends only on internet speed and not instance type. To give an idea of upload speed, it took me under 8 minutes to upload a 150MB compressed file on a busy 5 GH wifi connection. **Syntax for upload files:**

	-u C:\Data\file.txt  # uploading one file 
	-u C:\Data\file_1.txt,C:\MapData\file_2.zip  #uploading a list of files 

`-r` <br>
*Remotepath* is the directory of the EC2 instance to upload the files in the `-u` (upload) option to. If the **remotepath** specified is in an EFS that has been mounted on the instance that data will persist in the EFS and be accessible to any other instance that is mounted on that EFS, even if the current instance is terminated. For more on this see the **Elastic File System** section below. **Syntax for remotepath:**

	-r efs/data  # forward slash, this file will be placed in the home director. For example, in AWS Linux instance that is `home/ec2-user/`

`-a` <br>
*Activepath* is a boolean (`True` or `False`) for whether to leave an active shell connected to the instance after the scripts have finished running (if your instance has a linux ami, for example, this will be a linux shell).

<br><br>
## Elastic File System 

This script makes it easy to create and mount an elastic file system (EFS). You can specify the name of *new* EFS you want to create or the *existing* EFS you want to connect to using the `-f` (**filesystem**) option when running the script from the command prompt. At least one mount target (a sort of connection point) must be created for an EFS to connect to it, this script will automatically create or identify an existing mount target when an EFS is specified using the first IP address available to the block belonging to the instance subnet (for a full explanation of Subnets see https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Subnets.html).

When an EFS is specified, this script will automatically create the bash script `efs_mount.sh` in the local directory. To link an EFS to an instance the instance must request to connect to the EFS, that is what the bash script does. Once an EFS has been mounted onto an instance it does not need to be mounted again, even if you disconnect from that instance. 

### Data Persisitence

Elastic file systems are a type of file storage provided by AWS that expands as more data is added to it. Data can be added to the and EFS directly through an instance or via DataSync which is a separate process offered by AWS. Datasync can be setup and run using spot instances. Any data you add to an EFS will persist such that if you mount an instance, upload data to the EFS folder, terminate the instance, launch a new instance, connect that instance to the same EFS (which you can do easily with the `-f` option) the data you uploaded earlier will automatically be available in the new instance. This makes it easy to resume work and save results quickly. 


*Example data for the directory was downloaded from: https://data.world/datafiniti/wine-beer-and-liquor-reviews*

<br><br>
## Instance Type Selection 

Different hardware is might be more or less appropriate depending on the what you are using the instance for. The initial purpose for creating this module was to accelerate the execution of deep learning projects, however there are several steps in that process which include data transfer, management and cleaning. AMIs and instance types can be browsed in the AWS launch wizards and then specified in personalized profile dictionaries that can be submitted through the `-p` option. Nevertheless I provide a few pre-set profile types for different tasks. 

### Profile Types 

This list will be updated as more profiles are added. To see the specific values for each profile please check `spot_connect.py`. The pre-set profiles currently available are: 

`"default"` : an example instance with $0.004 max cost instance that will mount an EFS and kickoff with a deep learning image in `us-west-2` region. 

`"datasync"` : a $0.15 max cost instance that can be used to as a datasync agent to assist with transfers in `us-west-2` region, no EFS is mounted.  

`"gateway"` : (in progress) an instance that can be uses the AWS gateway AMI to provide a gateway for NFS ports that can be used in data transfers including datasync. 

