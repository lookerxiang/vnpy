# encoding: UTF-8

"""
双均线移动止损策略，适合用在螺纹钢日线上

"""
import datetime as dt

import numpy as np
import talib

import dataRecorder.drEngineEx as dre
from ctaAlgo.ctaTemplateEx import CtaTemplate


########################################################################
class StrategyDoubleSMA(CtaTemplate):
    """结合ATR和RSI指标的一个分钟线交易策略"""
    className = 'StrategySingleSMA'
    author = u'向律楷'

    # 策略参数
    trailingPercent = 5.0  # 百分比移动止损，必须用浮点数
    period = [5, 14]  # EMA周期

    # 策略变量
    bar = None  # K线对象
    barMinute = ''  # K线当前的分钟
    bufferSize = max(period)  # 需要缓存的数据的量，应该小于等于初始化数据所用的天数里的数据量，以使得程序可以立即进入交易状态。
    bufferCount = 0  # 目前已经缓存了的数据的计数
    initSize = 0
    initCount = 0  # 目前已经缓存了的数据的计数

    intraTradeHigh = 0  # 移动止损用的持仓期内最高价
    intraTradeLow = 0  # 移动止损用的持仓期内最低价

    highArray = np.zeros(bufferSize)  # K线最高价的数组
    lowArray = np.zeros(bufferSize)  # K线最低价的数组
    closeArray = np.zeros(bufferSize)  # K线收盘价的数组

    shortEma = 0
    shortCount = 0  # 目前已缓存的短期EMA计数
    shortArray = np.zeros(bufferSize)  # 短期EMA数组

    longEma = 0
    longCount = 0  # 目前已缓存的短期EMA计数
    longArray = np.zeros(bufferSize)  # 短期EMA数组

    Ravi = 0
    RaviCount = 0  # 目前已缓存的短期EMA计数
    RaviList = []  # 短期EMA数组

    orderList = []  # 保存委托代码的列表

    barCount = 0  # 程序执行过程中传入的k线根数，用于测试

    isBacktesting = False

    # 参数列表，保存了参数的名称
    paramList = ['name',
                 'className',
                 'author',
                 'vtSymbol',
                 'trailingPercent',
                 'period',
                 ]

    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'pos',
               'intraTradeHigh',
               'intraTradeLow'
               ]

    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(StrategyDoubleSMA, self).__init__(ctaEngine, setting)

        # 注意策略类中的可变对象属性（通常是list和dict等），在策略初始化时需要重新创建，
        # 否则会出现多个策略实例之间数据共享的情况，有可能导致潜在的策略逻辑错误风险，
        # 策略类中的这些可变对象属性可以选择不写，全都放在__init__下面，写主要是为了阅读
        # 策略时方便（更多是个编程习惯的选择）

        self.lastOrder = None

    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog(u'双EMA演示策略初始化')

        # ！！手动调用父类实现
        super(StrategyDoubleSMA, self).onInit()

        # 载入历史数据，并采用回放计算的方式初始化策略数值
        startDatetime = self.ctaEngine.strategyStartDate if self.inBacktesting else dt.datetime.now()
        initData = self.getLastKlines(max(self.period), period=dre.ctaKLine.PERIOD_1DAY, from_datetime=startDatetime)

        for bar in initData:
            self.updateData(bar)

        self.putEvent()

    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeCtaLog(u'双EMA演示策略启动')

        # 注册K线回调
        self.registerOnbar((dre.ctaKLine.PERIOD_1DAY,))

        self.putEvent()

    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog(u'双EMA演示策略停止')

        # 注销K线回调
        self.unregisterOnbar((dre.ctaKLine.PERIOD_1DAY,))
        
        self.putEvent()

    def updateData(self, bar):
        # 获取历史K线
        lastKLines = self.getLastKlines(max(self.period), dre.ctaKLine.PERIOD_1DAY, from_datetime=bar.datetime)

        # 将历史K线转换为计算所需数据数组
        self.highArray[-len(lastKLines):] = [b.high for b in lastKLines]
        self.lowArray[-len(lastKLines):] = [b.low for b in lastKLines]
        self.closeArray[-len(lastKLines):] = [b.close for b in lastKLines]

        # 计算指标数值
        self.shortEma = talib.MA(self.closeArray, self.period[0])[-1]  # 计算EMA
        self.shortArray[0:self.bufferSize - 1] = self.shortArray[1:self.bufferSize]  # 需要的EMA存储的数据列表
        self.shortArray[-1] = self.shortEma

        self.longEma = talib.MA(self.closeArray, self.period[1])[-1]  # 计算EMA
        self.longArray[0:self.bufferSize - 1] = self.longArray[1:self.bufferSize]  # 需要的EMA存储的数据列表
        self.longArray[-1] = self.longEma

        self.Ravi = abs((self.shortEma - self.longEma) / self.longEma * 100)  # 运动辨识指数，用于过震荡时的虚假信号
        self.RaviList.append(self.Ravi)
        print bar.datetime, self.Ravi

    # ----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        # 撤销之前发出的尚未成交的委托（包括限价单和停止单）
        for orderID in self.orderList:
            self.cancelOrder(orderID)
        self.orderList = []

        self.updateData(bar)

        # 判断是否要进行交易
        # 当前无仓位
        if self.pos == 0:
            self.intraTradeHigh = bar.high
            self.intraTradeLow = bar.low

            # 长短均线均向上，形成金叉或股价上穿短期均线买入开多仓。
            if self.closeArray[-1] > self.longArray[-1] and self.closeArray[-2] > self.longArray[-2] and \
                            self.closeArray[-3] > self.longArray[-3]:
                if self.closeArray[-1] > self.shortArray[-1] > self.shortArray[-2]:
                    if self.Ravi > 1.0:
                        orderID = self.buy(bar.close + 5, 1)
                        self.orderList.append(orderID)

            # 长短均线均向下，形成死叉或股价下穿短期均线卖出开空仓
            elif self.closeArray[-1] < self.longArray[-1] and self.closeArray[-2] < self.longArray[-2] and \
                            self.closeArray[-3] < self.longArray[-3]:
                if self.closeArray[-1] < self.shortArray[-1] < self.shortArray[-2]:
                    if self.Ravi > 1.0:
                        orderID = self.short(bar.close - 5, 1)
                        self.orderList.append(orderID)

        elif self.pos > 0:  # 卖出平仓
            # 计算多头持有期内的最高价，以及重置最低价
            self.intraTradeHigh = max(self.intraTradeHigh, bar.high)
            self.intraTradeLow = bar.low

            # 计算多头移动止损
            longStop = self.intraTradeHigh * (1 - self.trailingPercent / 100)

            # 计算突破均线止损
            if self.closeArray[-1] < self.longArray[-1] and self.closeArray[-2] < self.longArray[-2]:
                longStop = max(bar.close, longStop)  # 止损价格为多头移动止损和突破均线止损的最大值

            # 发出本地止损委托，并且把委托号记录下来，用于后续撤单
            orderIDs = self.sell(longStop, 1, stop=True)
            self.orderList.extend(orderIDs)

        elif self.pos < 0:  # 买入平仓
            # 计算多空持有期内的最低价，以及重置最高价
            self.intraTradeLow = min(self.intraTradeLow, bar.low)
            self.intraTradeHigh = bar.high
            # 计算空头移动止损
            longStop = self.intraTradeLow * (1 + self.trailingPercent / 100)
            # 计算突破均线止损
            if self.closeArray[-1] > self.longArray[-1] and self.closeArray[-2] > self.longArray[-2]:
                longStop = min(bar.close, longStop)
            orderIDs = self.cover(longStop, 1, stop=True)
            self.orderList.extend(orderIDs)

        # 发出状态更新事件
        self.putEvent()

    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        self.lastOrder = order

    def onMaPeriod(self, period):
        self.period = period

    def onInitDays(self, initDays):
        self.initDays = initDays


if __name__ == '__main__':
    # 提供直接双击回测的功能
    # 导入PyQt4的包是为了保证matplotlib使用PyQt4而不是PySide，防止初始化出错
    from ctaBacktesting import *
    from vtEngine import MainEngine
    import os

    path = os.path.join(os.path.dirname(__file__), '..')
    sys.path.append(path)

    # 创建回测引擎
    engine = BacktestingEngine()
    engine.mainEngine = MainEngine()
    engine.posBufferDict = {}

    # 在引擎中创建策略对象
    engine.initStrategy(StrategyDoubleSMA, dict(vtSymbol='RB0000', inBacktesting=True, period=[6,15]))  # 初始化策略

    # 设置引擎的回测模式为K线
    engine.setBacktestingMode(engine.BAR_MODE)

    # 设置回测用的数据起始日期
    engine.setStartDate('20090327', initDays=StrategyDoubleSMA.bufferSize * 2)
    engine.setEndDate('20170222')

    # 设置产品相关参数
    engine.setSlippage(1.0)  # 股指1跳
    engine.setRate(0.5 / 10000)  # 万0.3
    engine.setSize(10)  # 表示一手合约的数量，比如一手豆粕为10t，则size为10

    # 设置使用的历史数据库
    engine.setDatabase(DAILY_DB_NAME, engine.strategy.vtSymbol)
    # 设置策略所需的均线周期，便于ctaBacktesting中画均线
    #engine.setMaPeriod([5, 14])

    ## 开始跑回测-----------------------------------------------------------------------------
    engine.runBacktesting()

    ## 显示回测结果
    engine.showBacktestingResult()


    ## 跑优化---------------------------------------------------------------------------------
    #setting = OptimizationSetting()                 # 新建一个优化任务设置对象
    #setting.setOptimizeTarget('capital')            # 设置优化排序的目标是策略净盈利
    #setting.addParameter('atrLength', 12, 20, 2)    # 增加第一个优化参数atrLength，起始11，结束12，步进1
    #setting.addParameter('atrMa', 20, 30, 5)        # 增加第二个优化参数atrMa，起始20，结束30，步进1
    #setting.addParameter('rsiLength', 5)            # 增加一个固定数值的参数

    ## 性能测试环境：I7-3770，主频3.4G, 8核心，内存16G，Windows 7 专业版
    ## 测试时还跑着一堆其他的程序，性能仅供参考
    #import time
    #start = time.time()

    ## 运行单进程优化函数，自动输出结果，耗时：359秒
    #engine.runOptimization(AtrRsiStrategy, setting)

    ## 多进程优化，耗时：89秒
    ##engine.runParallelOptimization(AtrRsiStrategy, setting)

    #print u'耗时：%s' %(time.time()-start)