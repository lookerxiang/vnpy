# encoding: UTF-8

"""
单均线移动止损策略，适合用在螺纹钢日线上
"""

import datetime as dt
import time

import numpy as np

import dataRecorder.drEngineEx
from ctaAlgo.ctaTemplateEx import CtaTemplate


########################################################################
class StrategySingleSMASample(CtaTemplate):
    """结合ATR和RSI指标的一个分钟线交易策略"""
    className = 'StrategySingleSMASample'
    author = u'陈亚虎'

    # 策略参数
    trailingPercent = 5.0  # 百分比移动止损，必须用浮点数
    shortEmaLength = 12  # EMA周期

    # 策略变量
    bar = None  # K线对象
    barMinute = ''  # K线当前的分钟
    bufferSize = 12  # 需要缓存的数据的量，应该小于等于初始化数据所用的天数里的数据量，以使得程序可以立即进入交易状态。
    bufferCount = 0  # 目前已经缓存了的数据的计数
    initSize = 0
    initCount = 0  # 目前已经缓存了的数据的计数

    intraTradeHigh = 0  # 移动止损用的持仓期内最高价
    intraTradeLow = 0  # 移动止损用的持仓期内最低价

    highArray = np.zeros(bufferSize)  # K线最高价的数组
    lowArray = np.zeros(bufferSize)  # K线最低价的数组
    closeArray = np.zeros(bufferSize)  # K线收盘价的数组
    shortCount = 0  # 目前已缓存的短期EMA计数
    shortArray = np.zeros(bufferSize)  # 短期EMA数组
    orderList = []  # 保存委托代码的列表

    barCount = 0  # 程序执行过程中传入的k线根数，用于测试

    isBacktesting = False

    # 参数列表，保存了参数的名称
    paramList = ['name',
                 'className',
                 'author',
                 'vtSymbol',
                 'trailingPercent',
                 'shortEmaLength',
                 ]

    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'pos',
               'intraTradeHigh',
               'intraTradeLow'
               ]

    # ----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(StrategySingleSMASample, self).__init__(ctaEngine, setting)

        # 注意策略类中的可变对象属性（通常是list和dict等），在策略初始化时需要重新创建，
        # 否则会出现多个策略实例之间数据共享的情况，有可能导致潜在的策略逻辑错误风险，
        # 策略类中的这些可变对象属性可以选择不写，全都放在__init__下面，写主要是为了阅读
        # 策略时方便（更多是个编程习惯的选择）

    # ----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略初始化' % self.name)

        # 载入历史数据，并采用回放计算的方式初始化策略数值
        startDatetime = self.backtestingStartDatetime if self.inBacktesting else dt.datetime.now()
        initData = self.getLastKlines(10, from_datetime=startDatetime)

        print(initData)

        self.putEvent()
        self.writeCtaLog(u'策略初始化完成')

    # ----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略启动' % self.name)
        self.putEvent()

        # 注册K线回调
        self.registerOnbar((drEngineEx.ctaKLine.PERIOD_1MIN,))

    # ----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog(u'%s策略停止' % self.name)
        self.putEvent()

        # 注销K线回调
        self.unregisterOnbar((drEngineEx.ctaKLine.PERIOD_1MIN,))

    # ----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送"""
        pass

    # ----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        # 测试代码用
        print(bar)
        self.barCount += 1
        print(self.barCount, time.localtime())
        if self.barCount == 1:
            self.sell(100, 1, stop=True)
            print("发停止单")
        if self.barCount == 2:
            self.buy(bar.close + 5, 1)
            print("买多")
        if self.barCount == 3:
            self.sell(bar.close - 5, 2)
            print("卖空")
        if self.barCount == 4:
            self.sell(bar.close - 5, 1)
            print("卖空")

        self.putEvent()


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
    # d = {'atrLength': 11}
    engine.initStrategy(StrategySingleSMASample, dict(
            inBacktesting=True, backtestingStartDatetime=dt.datetime(2013, 8, 19) + dt.timedelta(20)))  # 初始化策略
    engine.strategy.vtSymbol = 'rb1705'
    engine.strategy.isBacktesting = True
    # 设置引擎的回测模式为K线

    engine.setBacktestingMode(engine.BAR_MODE)

    # 设置回测用的数据起始日期
    engine.setStartDate('20130819', initDays=20)
    engine.setEndDate('20170113')
    # 设置产品相关参数
    engine.setSlippage(0.2)  # 股指1跳
    engine.setRate(3 / 10000)  # 万0.3
    engine.setSize(10)  # 表示一手合约的数量，比如一手豆粕为10t，则size为10

    # 设置使用的历史数据库
    engine.setDatabase(MINUTE_DB_NAME, 'RB0000')

    ## 开始跑回测
    engine.runBacktesting()

    ## 显示回测结果
    engine.showBacktestingResult()

    # 跑优化--------------------------------------------------------------------------
    # setting = OptimizationSetting()                 # 新建一个优化任务设置对象
    # setting.setOptimizeTarget('capital')            # 设置优化排序的目标是策略净盈利
    # setting.addParameter('trailingPercent', 1.0, 10.0, 1.0)    # 增加第一个优化参数atrLength，起始11，结束12，步进1
    # setting.addParameter('shortEmaLength', 5, 30, 1)        # 增加第二个优化参数atrMa，起始20，结束30，步进1

    # 性能测试环境：I7-3770，主频3.4G, 8核心，内存16G，Windows 7 专业版
    # 测试时还跑着一堆其他的程序，性能仅供参考
    # import time
    # start = time.time()

    # 运行单进程优化函数，自动输出结果，耗时：359秒
    # engine.runOptimization(StrategySingleSMA, setting)

    # 多进程优化，耗时：89秒
    # engine.runParallelOptimization(AtrRsiStrategy, setting)

    # print u'耗时：%s' %(time.time()-start)
