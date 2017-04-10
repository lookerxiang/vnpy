# encoding: UTF-8

'''
在原生ctaBacktesting基础上定制自己的回测系统：
1、显示均线等
2、实现多周期。
'''
from ctaAlgo.ctaBacktesting import *
import numpy as np
import pandas as pd


########################################################################
class BacktestingEngineEx(BacktestingEngine):
    # ----------------------------------------------------------------------
    def __init__(self):
        super(BacktestingEngineEx, self).__init__()

        self.period = [5, 12]  # k线周期，默认为5和12
        self.backtestingData = []   # 回测用的数据

    # ----------------------------------------------------------------------
    # def setStartDate(self, startDate='20150416', initDays=10):
    #     """设置回测的启动日期"""
    #     self.startDate = startDate
    #     self.initDays = initDays
    #     self.dataStartDate = datetime.strptime(startDate, '%Y%m%d')  # 数据开始时间
    #     initTimeDelta = timedelta(initDays)
    #     self.strategyStartDate = self.dataStartDate + initTimeDelta  # 策略开始时间，即前面的数据用于初始化
        #self.strategy.onInitDays(self.initDays)

    # ----------------------------------------------------------------------
    def loadHistoryData(self):
        """载入历史数据"""
        host, port, logging = loadMongoSetting()

        self.dbClient = pymongo.MongoClient(host, port)
        collection = self.dbClient[self.dbName][self.symbol]

        self.output(u'开始载入数据')

        # 首先根据回测模式，确认要使用的数据类
        if self.mode == self.BAR_MODE:
            dataClass = CtaBarData
            func = self.newBar
        else:
            dataClass = CtaTickData
            func = self.newTick

        # 载入初始化需要用的数据
        flt = {'datetime': {'$gte': self.dataStartDate,
                            '$lt': self.strategyStartDate}}
        initCursor = collection.find(flt)

        # 将数据从查询指针中读取出，并生成列表
        self.initData = []  # 清空initData列表
        for d in initCursor:
            data = dataClass()
            data.__dict__ = d
            self.initData.append(data)
            self.backtestingData.append(d)

        # 载入回测数据
        if not self.dataEndDate:
            flt = {'datetime': {'$gte': self.strategyStartDate}}  # 数据过滤条件
        else:
            flt = {'datetime': {'$gte': self.strategyStartDate,
                                '$lte': self.dataEndDate}}
        self.dbCursor = collection.find(flt)

        self.output(u'载入完成，数据量：%s' % (initCursor.count() + self.dbCursor.count()))

    # ----------------------------------------------------------------------
    def runBacktesting(self):
        """运行回测"""
        # 载入历史数据
        self.loadHistoryData()

        # 首先根据回测模式，确认要使用的数据类
        if self.mode == self.BAR_MODE:
            dataClass = CtaBarData
            func = self.newBar
        else:
            dataClass = CtaTickData
            func = self.newTick

        self.output(u'开始回测')

        self.strategy.inited = True
        self.strategy.onInit()
        self.output(u'策略初始化完成')

        self.strategy.trading = True
        self.strategy.onStart()
        self.output(u'策略启动完成')

        self.output(u'开始回放数据')

        for d in self.dbCursor:
            data = dataClass()
            data.__dict__ = d
            func(data)
            self.backtestingData.append(d)  # 用于画图，便于检查策略是否按照自己的想法运行

        self.output(u'数据回放结束')

    # ----------------------------------------------------------------------
    def showBacktestingResult(self):
        """显示回测结果"""
        d = self.calculateBacktestingResult()

        # 输出
        self.output('-' * 30)
        self.output(u'第一笔交易：\t%s' % d['timeList'][0])
        self.output(u'最后一笔交易：\t%s' % d['timeList'][-1])

        self.output(u'总交易次数：\t%s' % formatNumber(d['totalResult']))
        self.output(u'总盈亏：\t%s' % formatNumber(d['capital']))
        self.output(u'最大回撤: \t%s' % formatNumber(min(d['drawdownList'])))

        self.output(u'平均每笔盈利：\t%s' % formatNumber(d['capital'] / d['totalResult']))
        self.output(u'平均每笔滑点：\t%s' % formatNumber(d['totalSlippage'] / d['totalResult']))
        self.output(u'平均每笔佣金：\t%s' % formatNumber(d['totalCommission'] / d['totalResult']))

        self.output(u'胜率\t\t%s%%' % formatNumber(d['winningRate']))
        self.output(u'盈利交易平均值\t%s' % formatNumber(d['averageWinning']))
        self.output(u'亏损交易平均值\t%s' % formatNumber(d['averageLosing']))
        self.output(u'盈亏比：\t%s' % formatNumber(d['profitLossRatio']))

        # 绘图
        import matplotlib.pyplot as plt

        fig = plt.figure(1)
        pCapital = plt.subplot(3, 1, 1)
        pCapital.set_ylabel("capital")
        pCapital.plot(d['capitalList'])

        pDD = plt.subplot(3, 1, 2)
        pDD.set_ylabel("DD")  # 最大回撤
        pDD.bar(range(len(d['drawdownList'])), d['drawdownList'])

        pPnl = plt.subplot(3, 1, 3)
        pPnl.set_ylabel("pnl")  # 净盈亏序列
        pPnl.hist(d['pnlList'], bins=50)

        # xlk自己修改---------------------------------------------------------------------------------------------------
        longtime = []  # 开多仓时间
        longprice = []  # 开多仓价格
        shorttime = []  # 开空仓时间
        shortprice = []  # 空仓价格
        closetime = [] #
        closeprice = []


        for trade in self.tradeDict.values():
            if trade.direction == DIRECTION_LONG and trade.offset == OFFSET_OPEN:
                longtime.append(trade.tradeTime)
                longprice.append(trade.price)
            elif trade.direction == DIRECTION_SHORT and trade.offset == OFFSET_OPEN:
                shorttime.append(trade.tradeTime)
                shortprice.append(trade.price)
            elif trade.offset == OFFSET_CLOSE:  # trade.direction == DIRECTION_LONG  and
                closetime.append(trade.tradeTime)
                closeprice.append(trade.price)

        timedata = []  # 提取收盘价与时间
        closedata = []
        for i in self.backtestingData:
            datadict = i
            d1 = datadict['datetime']
            timedata.append(d1)
            d2 = datadict['close']
            closedata.append(d2)


        fig = plt.figure(2)
        tradeplot = fig.add_subplot(1, 1, 1)
        tradeplot.plot(timedata, closedata, marker='.')
        tradeplot.plot(longtime, longprice, 'r^', label="duo")  #
        tradeplot.plot(shorttime, shortprice, 'g^', label='kong')
        tradeplot.plot(closetime, closeprice, 'ko', label='no')

        ts = pd.Series(closedata, index=pd.DatetimeIndex(timedata))
        # pd.rolling_mean(ts ,self.period).plot()
        if isinstance(self.period, list):  #如果是列表则循环
            for prd in self.period:
                ts.rolling(window=prd, win_type='boxcar').mean().plot()
        else:                              #否则
            ts.rolling(window=self.period, win_type='boxcar').mean().plot()

        tradeplot.legend(loc='best')
        plt.show()

    # ----------------------------------------------------------------------
    def setMaPeriod(self, period):
        """设置均线周期"""
        self.period = period  # 将周期赋值给BacktestingEngine类的实例的属性self.period
        self.strategy.onMaPeriod(self.period)  # 并将其回调给strategy。目的是使得二者的周期Ma一致

if __name__ == '__main__':
    # 以下内容是一段回测脚本的演示，用户可以根据自己的需求修改
    # 建议使用ipython notebook或者spyder来做回测
    # 同样可以在命令模式下进行回测（一行一行输入运行）
    from strategy.strategyEmaDemo import *
    
    # 创建回测引擎
    engine = BacktestingEngineEx()
    
    # 设置引擎的回测模式为K线
    engine.setBacktestingMode(engine.BAR_MODE)

    # 设置回测用的数据起始日期
    engine.setStartDate('20110101')
    
    # 载入历史数据到引擎中
    engine.setDatabase(MINUTE_DB_NAME, 'IF0000')
    
    # 设置产品相关参数
    engine.setSlippage(0.2)     # 股指1跳
    engine.setRate(0.3/10000)   # 万0.3
    engine.setSize(300)         # 股指合约大小    
    
    # 在引擎中创建策略对象
    engine.initStrategy(EmaDemoStrategy, {})
    
    # 开始跑回测
    engine.runBacktesting()
    
    # 显示回测结果
    # spyder或者ipython notebook中运行时，会弹出盈亏曲线图
    # 直接在cmd中回测则只会打印一些回测数值
    engine.showBacktestingResult()
    
    