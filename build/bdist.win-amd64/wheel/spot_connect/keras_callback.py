# -*- coding: utf-8 -*-
"""
Created on Sun Jul  5 21:40:55 2020

@author: Computer
"""

import keras, requests, time 

class SpotTermination(keras.callbacks.Callback):
    
    def __init__(self):
        '''The SpotTermination Class can be used in the callbacks list for any keras model. 
        At the beginning of each epoch the model will check if the spot instance has been scheduled for termination. 
        If it has then the process will sleep until termination in order to ensure an orderly shut-down.'''
        super(SpotTermination, self).__init__()

    def on_batch_begin(self, batch, logs={}):
        status_code = requests.get("http://169.254.169.254/latest/meta-data/spot/instance-action").status_code
        if status_code != 404: 
             time.sleep(150)
             
             
             
