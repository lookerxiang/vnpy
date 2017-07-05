# encoding: UTF-8

"""
对数据进行统计分析
"""

from __future__ import division
from datetime import datetime, timedelta

from ctaBase import *
from ctaTemplate import CtaTemplate
import pymongo
from vtFunction import loadMongoSetting
from vtConstant import *
from ctaBase import *

import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
import matplotlib

# matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.mlab as mlab
import talib

class Statistics(object):
    author = u'向律楷'

    TICK_MODE = 'tick'
    BAR_MODE = 'bar'
    # ----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        dbClient = None        # 数据库客户端
        self.dbCursor = None        # 数据库指针
        self.mode = self.BAR_MODE   # 回测模式，默认为K线
        # self.dataStartDate = None       # 回测数据开始日期，datetime对象
        # self.dataEndDate = None         # 回测数据结束日期，datetime对象
        self.data = []


    # ----------------------------------------------------------------------
    def loadHistoryData(self,dbName,symbol,dataStartDate,dataEndDate):
        """载入历史数据"""
        host, port, logging = loadMongoSetting()

        self.dbClient = pymongo.MongoClient(host, port)
        collection = self.dbClient[dbName][symbol]

        self.output(u'开始载入数据')

        # 首先根据回测模式，确认要使用的数据类
        if self.mode == self.BAR_MODE:
            dataClass = CtaBarData
        else:
            dataClass = CtaTickData

        # 载入回测数据
        dataStartDate=self.setStartDate(dataStartDate)
        dataEndDate=self.setEndDate(dataEndDate)
        if not dataEndDate:
            flt = {'datetime': {'$gte': dataStartDate}}  # 数据过滤条件
        else:
            flt = {'datetime': {'$gte': dataStartDate,
                                '$lte': dataEndDate}}
        self.dbCursor = collection.find(flt)
        # 将数据从查询指针中读取出，并生成列表
        self.data = []  # 清空initData列表
        for d in self.dbCursor:
            data0 = dataClass()
            data0.__dict__ = d
            self.data.append(data0)
        self.output(u'载入完成，数据量：%s' % (self.dbCursor.count()))


    # ----------------------------------------------------------------------
    def trueRangeStatistic(self, data):
        """真实波幅统计


        """
        self.output(u'开始统计真实波幅TR')
        highArray = np.zeros(len(data))  # K线最高价的数组
        lowArray = np.zeros(len(data))  # K线最低价的数组
        closeArray = np.zeros(len(data))  # K线收盘价的数组
        timeArray = []  # 时间

        i=0
        for bar in data:
            i+=1
            highArray[i-1]=bar.high
            lowArray[i-1] = bar.low
            closeArray[i-1] = bar.close
            timeArray.append(bar.datetime)
        TR=talib.TRANGE(highArray, lowArray, closeArray) #真实波幅
        ATR = talib.ATR(highArray, lowArray, closeArray, timeperiod=14) #平均真实波幅
        # NATR = talib.NATR(highArray, lowArray, closeArray, timeperiod=14)
        NTR=TR/closeArray
        NATR =ATR/closeArray  #相对平均真实波幅
        # 绘图

        #真实波幅及其移动平均------
        fig1 = plt.figure(u'历史k线及真实波幅')
        originalData = plt.subplot(3, 1, 1)
        originalData.set_ylabel("originalData")
        originalData.plot(timeArray, highArray)
        originalData.plot(timeArray, lowArray)
        originalData.plot(timeArray, closeArray)

        TRPlot = plt.subplot(3, 1, 2)
        TRPlot.set_ylabel("TR and ATR")
        TRPlot.plot(timeArray, TR,label="TR")
        TRPlot.plot(timeArray, ATR,label="ATR")

        TRPlot = plt.subplot(3, 1, 3)
        TRPlot.set_ylabel("NATR")
        TRPlot.plot(timeArray, NATR,label="NTR")

        #真实波幅统计------
        fig2 = plt.figure(u'真实波幅统计')
        # # example data
        # mu = 100  # mean of distribution
        # sigma = 15  # standard deviation of distribution
        # x = mu + sigma * np.random.randn(10000)
        #
        plt.subplot(2, 2, 1)

        num_bins = 150
        # # the histogram of the data
        n, bins, patches = plt.hist(np.nan_to_num(TR), num_bins, normed=1, facecolor='blue', alpha=0.5)
        # add a 'best fit' line
        mu=np.mean(TR[1:len(TR)])
        sigma=np.std(TR[1:len(TR)])
        y = mlab.normpdf(bins, mu, sigma)
        print mu,sigma
        plt.plot(bins, y, 'r--')
        plt.xlabel('TR')
        plt.ylabel('Probability')
        plt.title('Probability of TR')

        plt.subplot(2, 2, 2)
        # # the histogram of the data
        n, bins, patches = plt.hist(np.nan_to_num(NTR), num_bins, normed=1, facecolor='blue', alpha=0.5)
        # add a 'best fit' line
        mu = np.mean(NTR[1:len(NTR)])
        sigma = np.std(NTR[1:len(NTR)])
        y = mlab.normpdf(bins, mu, sigma)  #根据柱状图拟合正态分布概率密度函数
        print mu, sigma
        plt.plot(bins, y, 'r--')
        plt.xlabel('NTR')
        plt.ylabel('Probability')
        plt.title('Probability of NTR')
        # sns.distplot(np.nan_to_num(NTR), kde=False, fit=stats.expon)

        plt.subplot(2, 2, 3)
        # # the histogram of the data
        plt.hist(np.nan_to_num(TR), num_bins, normed=1, facecolor='blue',histtype='step', cumulative=True)
        plt.xlabel('TR')
        plt.ylabel('cumulative probability')
        plt.title('cumulative probability')

        plt.subplot(2, 2, 4)
        # # the histogram of the data
        plt.hist(np.nan_to_num(NTR), num_bins, normed=1, facecolor='blue', histtype='step', cumulative=True)
        plt.xlabel('NTR')
        plt.ylabel('cumulative probability')
        plt.title('cumulative probability')


        #平均真实波幅统计------
        fig3 = plt.figure(u'平均真实波幅统计')
        # # example data
        # mu = 100  # mean of distribution
        # sigma = 15  # standard deviation of distribution
        # x = mu + sigma * np.random.randn(10000)
        #
        plt.subplot(2, 2, 1)

        num_bins = 150
        # # the histogram of the data
        n, bins, patches = plt.hist(np.nan_to_num(ATR), num_bins, normed=1, facecolor='blue', alpha=0.5)
        # add a 'best fit' line
        mu = np.mean(ATR[14:len(ATR)])
        sigma = np.std(ATR[14:len(ATR)])
        y = mlab.normpdf(bins, mu, sigma)
        print mu, sigma
        plt.plot(bins, y, 'r--')
        plt.xlabel('ATR')
        plt.ylabel('Probability')
        plt.title('Probability of ATR')

        plt.subplot(2, 2, 2)
        # # the histogram of the data
        n, bins, patches = plt.hist(np.nan_to_num(NATR), num_bins, normed=1, facecolor='blue', alpha=0.5)
        # add a 'best fit' line
        mu = np.mean(NATR[14:len(NATR)])
        sigma = np.std(NATR[14:len(NATR)])
        y = mlab.normpdf(bins, mu, sigma)  # 根据柱状图拟合正态分布概率密度函数
        print mu, sigma
        plt.plot(bins, y, 'r--')
        plt.xlabel('NATR')
        plt.ylabel('Probability')
        plt.title('Probability of NATR')
        # sns.distplot(np.nan_to_num(NTR), kde=False, fit=stats.expon)

        plt.subplot(2, 2, 3)
        # # the histogram of the data
        plt.hist(np.nan_to_num(ATR), num_bins, normed=1, facecolor='blue', histtype='step', cumulative=True)
        plt.xlabel('ATR')
        plt.ylabel('cumulative probability')
        plt.title('cumulative probability')

        plt.subplot(2, 2, 4)
        # # the histogram of the data
        plt.hist(np.nan_to_num(NATR), num_bins, normed=1, facecolor='blue', histtype='step', cumulative=True)
        plt.xlabel('NATR')
        plt.ylabel('cumulative probability')
        plt.title('cumulative probability')
        plt.show()
        # 画资金曲线的移动平均线
        # ts = pd.Series(d['capitalList'], index=pd.DatetimeIndex(d['timeList']))
        # ts.rolling(window=20, win_type='boxcar').mean().plot()


        self.output(u'统计真实波幅TR完成')

    # ------------------------------------------------------------------------------------------------------------------
    def ravi(self, data,shortPeriod,longPeriod):
        """
        Parameters
        ----------
        data: 输入数据

        Returns
        -------
        """
        self.output(u'开始统计真实波幅TR')
        highArray = np.zeros(len(data))  # K线最高价的数组
        lowArray = np.zeros(len(data))  # K线最低价的数组
        closeArray = np.zeros(len(data))  # K线收盘价的数组
        timeArray = []  # 时间
        i = 0
        for bar in data:
            i += 1
            highArray[i - 1] = bar.high
            lowArray[i - 1] = bar.low
            closeArray[i - 1] = bar.close
            timeArray.append(bar.datetime)

        shortMa = talib.MA(closeArray, shortPeriod)  # 计算EMA
        longMa = talib.MA(closeArray, longPeriod)  # 计算EMA
        ravi = abs((shortMa - longMa) / longMa * 100)  # 运动辨识指数，用于过震荡时的虚假信号
        aravi=np.nan_to_num(talib.MA(ravi,8))

        sigma = np.nan_to_num(talib.STDDEV(closeArray, timeperiod=8, nbdev=1))

        # 绘图--------------------------------------------
        fig1 = plt.figure(u'历史k线及动辨识指数')
        originalData = plt.subplot(3, 1, 1)
        originalData.set_ylabel("originalData")
        # originalData.plot(timeArray, highArray)
        # originalData.plot(timeArray, lowArray)
        originalData.plot(timeArray, closeArray)

        TRPlot = plt.subplot(3, 1, 2)
        TRPlot.set_ylabel("ravi")
        TRPlot.plot(timeArray, ravi, label="ravi")
        TRPlot.plot(timeArray, aravi, label="aravi")

        TRPlot = plt.subplot(3, 1, 3)
        TRPlot.set_ylabel(" Standard Deviation")
        TRPlot.plot(timeArray, sigma, label="sigma")



        plt.show()

    # ----------------------------------------------------------------------
    def output(self, content):
        """输出内容"""
        print str(datetime.now()) + "\t" + content

    # ----------------------------------------------------------------------
    def setStartDate(self, dataStartDate='20100416'):
        """设置回测的启动日期"""

        dataStartDate = datetime.strptime(dataStartDate, '%Y%m%d')
        return dataStartDate



    # ----------------------------------------------------------------------
    def setEndDate(self, endDate=''):
        """设置回测的结束日期"""
        if endDate:
            dataEndDate = datetime.strptime(endDate, '%Y%m%d')
            # 若不修改时间则会导致不包含dataEndDate当天数据
            dataEndDate.replace(hour=23, minute=59)
            return dataEndDate



if __name__ == '__main__':
    test=Statistics()
    test.loadHistoryData(DAILY_DB_NAME,'RB0000','20151209','20170819')
    # test.trueRangeStatistic(test.data)
    test.ravi(test.data,8,16)

