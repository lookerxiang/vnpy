#!/usr/bin/env python
# coding=utf-8

import matplotlib.pyplot as plt
import matplotlib.mlab as mlab

from matplotlib.dates import DateFormatter, WeekdayLocator, DayLocator, MONDAY,YEARLY
from matplotlib.finance import quotes_historical_yahoo_ochl , candlestick_ohlc

import numpy as np

def main():
    # plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False

    ticker = '600000' # 600028 是"中国石化"的股票代码
    ticker += '.ss'   # .ss 表示上证 .sz表示深证

    date1 = (2015, 8, 1) # 起始日期，格式：(年，月，日)元组
    date2 = (2016, 1, 1)  # 结束日期，格式：(年，月，日)元组


    mondays = WeekdayLocator(MONDAY)            # 主要刻度
    alldays = DayLocator()                      # 次要刻度
    #weekFormatter = DateFormatter('%b %d')     # 如：Jan 12
    mondayFormatter = DateFormatter('%Y-%m-%d') # 如：2-29-2015
    dayFormatter = DateFormatter('%d')          # 如：12

    quotes = quotes_historical_yahoo_ochl(ticker, date1, date2)

    if len(quotes) == 0:
        raise SystemExit

    fig, ax = plt.subplots()
    fig.subplots_adjust(bottom=0.2)

    ax.xaxis.set_major_locator(mondays)
    ax.xaxis.set_minor_locator(alldays)
    ax.xaxis.set_major_formatter(mondayFormatter)

    #plot_day_summary(ax, quotes, ticksize=3)
    candlestick_ohlc(ax, quotes, width=0.6, colorup='r',colordown='g')

    ax.xaxis_date()
    ax.autoscale_view()
    plt.setp(plt.gca().get_xticklabels(), rotation=45, horizontalalignment='right')

    ax.grid(True)
    plt.title('600028')
    plt.show()
    return

if __name__ == '__main__':
    main()