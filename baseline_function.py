# -*- coding: utf-8 -*-
"""
Created on Sat Oct 26 02:08:18 2019

@author: sumedh
"""

import os
import pandas as pd
from pandas import Timestamp, date_range, Timedelta
from glob import glob
from holidays import get_holidays

def weather_adjustment(start, end, meter, basis_dates):
    '''
    Provides the gross adjustment factor for weather adjusted baselines
    
    Parameters:
        start (str) : A str coercile to timestamp for the start of the event
        end (str) : A str coercile to timestamp for the end of the event
        meter (dataframe): A dataframe consisting of datetime and load values
        basis_dates (list) : A list of dates 
    
    Return:
        float : A float which gives the weather adjustment factor
        
    '''
    start = Timestamp(start)
    end = Timestamp(end)
    # adjustment hours 4 hour prior to start of event
    adj_hrs = list(range(start.hour -4, start.hour - 2))
    # get adjustment on the day of the event
    adj_usage = meter[(meter.date == start.date()) & (meter.hour.isin(adj_hrs))]
    adj_usage = adj_usage.groupby('hour').mean()
    adj_usage = adj_usage.mean()
    
    adj_basis = meter[(meter.date.isin(basis_dates)) & (meter.hour.isin(adj_hrs))]
    adj_basis = adj_basis.groupby('hour').mean()
    adj_basis = adj_basis.mean()
    
    return adj_usage/adj_basis


def perf_calc(df, hrs):
    '''
    Calculates the event performance per hour
    Parameters:
        df (dataframe) : A dataframe containing actual load and baseline values
        hrs (list) : A list of relevant hours
    
    Returns:
        pandas dataframe
    '''
    df = df[df.hour.isin(hrs)]
    df['perf'] = df['adjustment'] - df['kW']
    
    return df


def nyiso_cbl(meter, event_start, event_end, look_back, event_type = 'weekday'):
    '''
    calculates the nysio customer baseline given the input parameters
    
    Parameters:
        meter (dataframe): A dataframe consisting of datetime and load values
        event_start (str) : A str coercile to timestamp for the start of the event
        event_end (str) : A str coercile to timestamp for the end of the event
        look_back (int) : An integer specifying the number of days to look back
        event_type (str) : A string specifying the type of event (weekday, sunday, saturday)
        
    Returns:
        tuple : A tuple of dataframe which give the baselins and the performance for the event hour
    '''
    start = Timestamp(event_start)
    end = Timestamp(event_end)
    event_hours = date_range(start, end, freq = 'H').hour.tolist()
    event_hours = event_hours[:-1] # accounting for hour ending
    # get max lookback days
    window_start = start.date() - Timedelta(look_back, unit = 'days')
    datelist = date_range(window_start, periods = look_back).date.tolist()
    data = meter[meter.date.isin(datelist)]
    #TODO: weekend cbl logic
    if event_type == 'weekday':
        days = list(range(1,6))
    
    if event_type == 'saturday':
        days = [6]
        
    if event_type == 'sunday':
        days = [7]
    
    #get the seed values
    seed_data = data[data.hour.isin(event_hours)]
    seed_data = seed_data[seed_data['date'] != start.date()]
    seed_data = seed_data.groupby(['date','hour']).mean().reset_index()
    seed_value = seed_data['kW'].max()*0.25
    
    # identify the low usage days
    low_usage = seed_data.groupby(['date']).mean()
    low_usage_dates = low_usage[low_usage.kW < seed_value].index.tolist()
    
    rm_day = [d for d in seed_data.date.to_list() if not d.isoweekday() in days]
    rm_day = list(set(rm_day))
    # get dates and holidays to exclude
    exclude = get_holidays(start.year)
    exclude.extend(low_usage_dates)
    exclude.extend([start.date()-Timedelta(1, unit = 'day')])
    exclude.extend(rm_day)
    
    # get cbl basis days 
    max_days = seed_data.date.unique().tolist()
    days_to_keep = [d for d in max_days if d not in exclude]
    days_to_keep.sort(reverse = True)
    
    if len(days_to_keep) > 10:
        cbl_basis = days_to_keep[:10]
    else:
        cbl_basis = days_to_keep
    
    #get averages and rank them, pick the top 5 of the averages
    averages = seed_data.groupby('date').mean()
    averages = averages[averages.index.isin(cbl_basis)]
    averages['rank'] = averages['kW'].rank(ascending = False)
    baseline_dates = averages[averages['rank'] <= 5].index.tolist()
    
    # calculate baseline as average of the hours for the selected days
    baseline = data[data.date.isin(baseline_dates)]
    baseline = baseline.groupby('hour').mean()
    # actual values during event day
    event_day = meter[meter.dttm >= start.floor('24H')]
    event_day = event_day[event_day.dttm < start.ceil('24H')]
    event_day = event_day.groupby(['id','hour']).mean().reset_index()
    event_day['baseline'] = baseline.kW
    
    #get adjustment factor
    gaf = weather_adjustment(start = start, end = end, meter = meter,
                             basis_dates = cbl_basis)
    # get the adjusted baseline
    event_day['adjustment'] = event_day.baseline * gaf.kW
    # calculate the event performance per hour
    perf = perf_calc(event_day, event_hours)
    
    return event_day, perf


def read_format_transform(file):
    '''
    Reads data files and transforms kwh to kw depending on the granularity
    
    Parameters:
        files (str): A string path for the data files
    
    Return:
        pandas dataframe
    '''
    site = file.split('\\')[-1].split('.')[0]
    df = pd.read_csv(file)
    df['id'] = site
    df.columns = ['dttm','kWH','id']
    df['dttm'] = pd.to_datetime(df['dttm'])
    trf = 60/(df.dttm - df.dttm.shift()).mean().components.minutes
    df['kW'] = df['kWH']*trf
    df.drop(['kWH'], axis = 1, inplace = True)
    df['hour'] = df.dttm.dt.hour
    df['date'] = df.dttm.dt.date
    df['day'] = df.dttm.dt.dayofweek
    
    return df


# =============================================================================
data_files = glob(os.getcwd()+'\data\*')
event_start  = '06-13-17 2:00 PM'
event_end = '06-13-17 - 6:00PM'
df = []    
performance = []
look_back = 30
for file in data_files:
    meter = read_format_transform(file)
    baseline, perf = nyiso_cbl(meter, event_start, event_end, look_back)
    df.append(baseline)
    performance.append(perf)

all_baselines = pd.concat(df)
all_baselines.to_csv('baseline.csv',index = False)
all_performance = pd.concat(performance)
all_performance.to_csv('performance.csv', index = False)
#     
# 
# =============================================================================

