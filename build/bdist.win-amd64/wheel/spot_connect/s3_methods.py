"""
Author: Carlos Valcarcel <carlos.d.valcarcel.w@gmail.com>

This file is part of spot-connect

Toolbox for launching an AWS spot instance - s3_methods.py: 

The s3_methods sub-module contains functionalized tasks that use boto3 to 
interact with objects on s3. 
    
MIT License 2020
"""

import os
from path import Path 

root = Path(os.path.dirname(os.path.abspath(__file__)))

from spot_connect.sutils import chunks

import boto3
from Ipython.display import clear_output 

def listS3Objects(bucket_name):
    s3 = boto3.resource('s3')

    bucket = s3.Bucket(bucket_name)

    s3_files = [] 
    i = 0 
    for f in bucket.objects.all():
        s3_files.append(f)
        i+=1 
        if i%100==0:
            print(f)
            print('object #:', i)
            clear_output(wait=True)

    return s3_files 

def deleteS3Objects(bucket_name : str, objects : list): 
    '''
    Delete a list of s3 objects from a given s3 bucket
    '''

    assert type(objects[0]) == boto3.resources.factory.s3.ObjectSummary
    
    s3 = boto3.resource('s3')

    bucket = s3.Bucket(bucket_name)


    file_chunks = [c for c in chunks(objects, 1000)]
    
    responses = []
    
    for files in file_chunks: 
        ftod = [{'Key':c.key} for c in files]
        response = bucket.delete_objects(
            Delete={'Objects': ftod}
        ) 
        responses.append(response)