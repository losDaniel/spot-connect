mkdir ~/efs &> /dev/null
sudo mount -t nfs -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport fs-7b2103d0.efs.us-west-2.amazonaws.com:/   ~/efs 
cd ~/efs
sudo chmod go+rw .
mkdir ~/efs/data &> /dev/null
