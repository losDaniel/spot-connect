sudo yum -y install nfs-utils
# create the directory "efs-mount-point" in the instance 
mkdir ~/efs-mount-point
# connect the EFS to that directory 
sudo mount -t nfs -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport <file system dns>:/   ~/efs-mount-point 
cd ~/efs-mount-point
sudo chmod go+rw .
