import os 
import pandas as pd 
import pip._internal

try:
    import statsmodels.api as sms
except:
    pip._internal.main(['install', 'statsmodels'])
    import statsmodels.api as sms

data = pd.read_csv(os.getcwd()+'/data/wine_beer_liquor_reviews.csv')

data = pd.concat([data,pd.get_dummies(data['brand'], prefix='B_')],axis=1)

ols = sms.OLS(data['reviews.rating'],data[[c for c in data.columns if 'B_' in c]])
results = ols.fit() 

with open('example_results.txt', 'w') as f: 
    f.write(str(results.summary2()))
    f.close()