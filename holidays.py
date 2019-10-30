# -*- coding: utf-8 -*-
"""
Created on Sat Oct 26 02:45:20 2019

@author: sumedh
"""

# https://stackoverflow.com/questions/33094297/create-trading-holiday-calendar-with-pandas
import datetime as dt
from pandas.tseries.holiday import AbstractHolidayCalendar, Holiday, nearest_workday, \
    USMartinLutherKingJr, USPresidentsDay, GoodFriday, USMemorialDay, \
    USLaborDay, USThanksgivingDay


class USCalendar(AbstractHolidayCalendar):
    rules = [
        Holiday('NewYearsDay', month=1, day=1, observance=nearest_workday),
        USMartinLutherKingJr,
        USPresidentsDay,
        GoodFriday,
        USMemorialDay,
        Holiday('USIndependenceDay', month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday('Christmas', month=12, day=25, observance=nearest_workday)
    ]


def get_holidays(year):
    inst = USCalendar()
    dates = inst.holidays(dt.date(year-1, 12, 31), dt.date(year, 12, 31))
    
    return dates.date.tolist()

