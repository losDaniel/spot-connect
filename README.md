# Spot Connect

__Note to reader__: This module requires you to setup an AWS account as well as the proper permissions within that account. This README is still in progress and does not include full walkthrough despite the module being operational.  

`pip install spot-connect`

## Dependencies 

The only dependency that MUST be installed by the user is the `awscli`: 

`pip install awscli` 

Once the awscli (AWS command line interface) has been installed you must configure it by typing: 

`aws configure` 

and then entering your credentials and default region. This will make sure that any connection requests you make to AWS are automatically directed to your account without needing to enter any sort of login credentials. 

Go to [this link](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html) for a more detailed explanation of `aws configure`. 

The rest of the package dependencies are installed automatically: 

- `boto3` 

- `netaddr` 

- `paramiko`

- `path` 

## Spot Instances:

Spot instances are excess capacity that AWS rents out at a discount through a bidding mechanism. Users can set a maximum price to bid on any excess capacity of any type of hardware loaded with any type of os image. 

Using this module users may: 

**1)** launch a spot instance with any capacity and image they like from a command prompt, script or notebook.

**2)** create elastic file systems (EFS) to that can be mounted on any number of instances for immediate data access. 

**3)** using a command prompt, open a prompt that is directly linked to any running instance 

**4)** perform a number of other essential tasks such as executing scripts and commands, uploading data directly to an instance, transfer data from S3 to EFS and back, and more. 

**Warning**:

Because spot instances rely on excess capacity they can be requisitioned by Amazon when demand increases, this gives users a 2 minute window to close their session and abandon the spot instance, forcing any unfinished work to resume on another spot instance should that be the user's choice. Read more about this in the **Suggested Project Guidelines** section below. 
 	
## Command Line Argument

`spot_connect -n <name> -p <profile> -s <scripts to run> -f <filesystem> -u <files or dir to upload> -r <path on instance to upload to> -a <active shell> -t <terminate instance> -m <enable cloud monitoring for the instance> -em <connect to or create a filesystem> -nm <create a new mount for the EFS> -ip <instance profile access>`

The `connect.py` script can be executed from the command line to launch or reconnect to an instance, mount an elastic files system, upload files, execute scripts and leave an active shell connected to the instance open in your command line. 

Launching an instance is as easy as:  

`spot_connect -n instance_1 -p default -a True` 

This will create an instance that will appear with the name "instance_1" in you EC2 concole, it will launch it with the default profile and instance type and leave an open prompt that is connected to the instance on your command prompt. 

**Options**

`-n` <br>
*Name* for the spot instance, a key and security group will be created for the instance with this name. The private key will be saved to the directory in a .pem file. 

`-p` <br>
*Profile* dictionary of parameters that describe the instance to be launched, the list of predefined profiles can be viewed using `spot_connect.sutils.load_profiles()`. 

`-s` <br>
*Script* path or list of paths to scripts to be executed. If you're running linux os on your instance these should be bash scripts. 

`-f` <br>
*Filesystem* creation token name. The `--efsmount` option must be set to True for this to have an effect. The name of the filesystem you want to connect to, if it does not exist one will be created and connected to. 

`-u` <br>
*Upload* is the file path or directory that will be uploaded via paramiko ssh transfer. Upload speed depends only on internet speed and not instance type. **

__Example for upload files__:

	-u C:\Data\file.txt  # uploading one file 
	-u C:\Data\file_1.txt,C:\MapData\file_2.zip  #uploading a list of files 

`-r` <br>
*Remotepath* is the directory on the EC2 instance to upload the files in the `-u` (upload) option to. 

 **Syntax for remotepath:**

	-r /home/ec2-user/efs/data  

`-a` <br>
*Activeprompt* is a boolean (`True` or `False`) for whether to leave an active shell connected to the instance after the scripts have finished running (if your instance has a linux ami, for example, this will be a linux shell).

`-t`<br>
*Terminate* is a boolean. If "True" the instance specified in the `-n` (name) argument will be terminated and nothing else will be done (*Terminate* overrides all other arguments). 

`-m`<br>
*Monitoring* if set to True will activate cloudwatch monitoring for the instance. 

`-em`<br>
*EFSMount* if set to True will connect to the EFS specified in the `-f` arg or create an EFS with that name if none exists. 

`-nm`<br> 
*Newmount* if set to True will create a new mount to an EFS for this instance. This is rarely necessary. 

`-ip`<br> 
*Instanceprofile* attaches a given instance profile to your instance to grant it access to other **AWS** services. 

**Launching vs. reconnecting to an instance**

The settings you may define only when launching an instance are: 
- profile
- monitoring 
- instance_profile 

__example__: 

`spot_connect -n VM1 -p t3.small -m True -ip role1`  

Once an instance is launched with these settings they are fixed and do not need to be defined again when connecting, such that I could open a prompt onto the instance using:

`spot_connect -n VM1 -a True`

and the instance would already be on a t3 processor with monitoring enabled and the instance_profile "role1" 

__Changing these specific settings after an instance has been created can be done but has not been incorporated into this module because, given the temporary nature of spot instances, relaunching the instance is an easier alternative.__ 

## SpotInstance Class

`from spot_connect.spotted import SpotInstance`

The `SpotInstance` class in the `spotted` module can be imported and run from scripts and notebooks and has all the same functionality of the command line tool. 

`my_instance = SpotInstance('VM1', profile="t3.small", monitoring=True, instance_profile="role1")`

The `my_instance` variable instantiated above would connect to or create an instance called "VM1" with profile "t3.small," cloudwatch monitoring enables and instance profile "role1."

The `SpotInstance` class even lets you define some of the profile settings directly such as,*image_id*, *instance_type*, *price*, *region*, and *firewall* (firewall settings). It even lets you specify some more detailed options such as the *key_pair*, *kp_dir* (key-pair directory), and *sec_group* (security group). In fact, the only option that is available in the command line and NOT available through the `spotted` module is `activeprompt`. 

However, the `SpotInstance` class does provide other functionality that makes it easier to handle and just as useful as the command line tool: 

- **`upload`**: upload files from a local directory directly to the instance. 

`my_instance.upload(files, remotepath)`

- **`download`**: download files from the instance to a local directory 

`my_instance.download(files, localpath)`

- **`run`**: run scripts or commands on the instance. 

`my_instance.run('my_script.sh')` # Runs a script called my_script.sh

`my_instance.run('ls', cmd=True)` # Runs the "ls" command on the instance and prints out the directory of the home folder. 

Scripts can be converted into strings where each command is separated by a "\n" character to avoid creating files. For example: 

	my_instance.upload('C://list_efs_files.py', '/home/ec2-user/efs/')
	results = my_instance.run('cd efs\n python list_efs_files.py', cmd=True, return_output=True) 

The first line uploads a python script to the "efs" directory where my elastic file system is mounted.
The second line changes the working direcotry to the "efs" direcotry and then runs the python file I just uploaded. The `cmd` option tells the `run` method that I've submitted a command and not a script, the `return_output` option redirects any printed output to the "results" variable. 

## LinkAWS Class

`from spot_connect.link import LinkAWS`

The `LinkAWS` class takes the `spotted` module one step further and provides the functionality for users to handle multiple spot instances and distribute workloads across these. 

`my_link = LinkAWS()` 

This provides useful functionality that makes working with the entire `spot_connect` module much easier, for example:

- **`launch_instance`** : Launch a spot instance and store it in the `LinkAWS.instances` dict attribute.

- **`instance_s3_transfer`** : Will launch a new instance to transfer files from an S3 bucket to an instance or vice-versa. An instance profile with S3 access must be defined otherwise an error will be returned. See section on instance profiles below. 

- **`clone_repo`**, **`update_repo`** : Clone/update a git repo on the instance. 

- **`run_distributed_jobs`** : Distribute scripts and workloads across a given number of instances with a given profile

The `LinkAWS` class also provides shortcuts for some utility functions such as: 

- **`get_instance_home_directory`** : prints the home directory for a given instance so the user can specify instance paths easily. 

- **`count_cores`** : prints the number physical and logical cores on a given instance.

- **`list_profiles`** : same as `spot_connect.sutils.load_profiles()`


## Suggested Project Guidelines

**Make sure your work can be stopped and resumed programatically**. As mentioned at the outset of this document, some instances may be requisitioned by AWS and force your work to stop. This is more likely if you are working on high capacity instances. Later versions of this module will make it possible for you to anticipate these shut-downs so you can save your work and then launch another instance immediately and resume in the same elastic file system. 

*Note: the functionality to detect when an instance is being shut-down is still in development*

<br><br>
# AWS

## [Elastic File System](https://aws.amazon.com/efs/)

Elastic file systems are a type of file storage provided by AWS that expand as more data are added to them. Data can be added to the and EFS directly through an instance or via DataSync which is a separate process offered by AWS. 

Any data you add to an EFS will persist such that if you mount an instance, upload data to the EFS folder, terminate the instance, launch a new instance, connect that instance to the same EFS (which you can do easily with the `-f` option) the data you uploaded earlier will automatically be available in the new instance. This makes it easy to resume work and save results quickly. 

**Connecting an Instance to an EFS**:

You can specify the name of *new* EFS you want to create or the *existing* EFS you want to connect to using the `-f` (**filesystem**) option when launching instances from the command line or `spotted` module. 

At least one mount target (a connection point) must be created for an EFS to connect to an instance. This module will automatically create or identify existing mount targets for a given EFS and will connect to it using the first IP address available in the subnet (for a full explanation of Subnets see https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Subnets.html).

To link an EFS to an instance the **instance** must request to connect to the EFS. When an instance is launched an an EFS is specified the module connects to the instance and runs a script that makes this request. Once an EFS has been mounted onto an instance it does not need to be mounted again, even if you disconnect from that instance. 

<br><br>
## Instance Types & Images 

AWS makes different hardware available for instances, you can select the hardware you want for your instance when you select the instance type. For a full list of instance types check [this link](https://aws.amazon.com/ec2/instance-types/).

Images or AMIs are the pre-set configurations available for instances. To my knowledge, every AMI in a given region is available for every instance type available in that region. You can browse through many pre-set AMIs can be browsed in the AWS EC2 launch wizard and then specified in profiles.

## Profiles & Specifying Instance Specs 

The profiles that come with the module can be viewed by using `spot_connect.sutils.load_profiles()`. These are stored in a file called "profiles.txt" which is installed along with the module. 

The "profiles.txt" file only contains a dictionary with different instance spec configurations that have been created for the user's convenience.

**Users will have to edit "profiles.txt" to fit their own aws configurations**:

- **region** : Almost every other setting is dependent on region. You can change all the regions in every profile listed in "profiles.txt" using `spot_connect.sutils.change_default_region(<region>)`

- **image_id** : The default AMI is the deep learning image for Linux, this can be changed for every profile listed in "profiles.txt" using `spot_connect.sutils.change_default_image(<image id>)`

- **price** : Price is the maximum price you are willing to bid for an instance. For a list of spot-instance prices check [this link](https://aws.amazon.com/ec2/spot/pricing/). Price varies by region so make sure you edit these accordingly in "profile.txt" if you change regions. 

- **username** : Usually "ec2-user" but can depend on the instance AMI. For a list of default usernames see: https://alestic.com/2014/01/ec2-ssh-username/

There is really no need to change any of the other settings in the any of the profiles listed in "profiles.txt"

## Instance Profiles 

Instance profiles are rolls that you can create and assign to instances in order to grant them access to other AWS resources such as S3. Read more about what they are and how to use them in [this link](https://docs.aws.amazon.com/codedeploy/latest/userguide/getting-started-create-iam-instance-profile.html). 

If you navigate to the IAM resource in your AWS dashboard you can create access roles specific for EC2 instances to access other resources. Once these roles have been created you can create an instance profile from a shell, script or notebook using the `boto3` module: 

```
import boto3

# Connect to the IAM client 
iam_client = boto3.client('iam')

# Create an instance profile
iam_client.create_instance_profile(
    InstanceProfileName = 'ec2_and_s3',
)

# Connect to the resource and the instance profile you've just created 
iam_resource = boto3.resource('iam')
instance_profile = iam_resource.InstanceProfile('ec2_and_s3')

# Add the desired IAM role, this should have been created earlier in the AWS console
instance_profile.add_role(RoleName='full_s3_access')
```

In the above block of code we create an instance profile names "ec2_and_s3" and assign it the access role "full_s3_access" which I created earlier through the dashboard. 

You know an instance has successfully been granted access because if you open a prompt to the instance and type `aws configure` your keys will already be filled. 