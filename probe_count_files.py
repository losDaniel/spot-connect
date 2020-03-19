# -*- coding: utf-8 -*-
"""
Created on Mon Jan 20 18:53:33 2020

@author: carlo
"""

import os 

def absoluteFilePaths(directory):
    for dirpath,_,filenames in os.walk(directory):
        for f in filenames:
            yield os.path.abspath(os.path.join(dirpath, f))
           
print('Number of files is ', len(list(absoluteFilePaths(os.getcwd()))), flush = True)