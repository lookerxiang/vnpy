# encoding: UTF-8

"""
在原vnpy策略模板基础上进行了扩展，支持以下功能：
1. 添加inBacktesting标志字段，区分实盘和回测环境
2. 策略初始化时从ctaEngine中自动获取pos
3. 买平、卖平考虑上期所平今平昨问题
4. 封装K线回调注册以及历史K线获取API，对应实盘和回测

注意：
onInit和onTrade有实现代码，重写时需手动调用！
"""

import bisect
import itertools

import pymongo

from ctaAlgo.ctaBase import *
from ctaAlgo.ctaTemplate import CtaTemplate as CtaTemplateOrginal
from dataRecorder import drEngineEx
from vtConstant import *

STRATEGY_TRADE_DB_NAME = 'VnTrader_Strategy_Order_Db'


########################################################################
class CtaTemplate(CtaTemplateOrginal):
    """CTA策略模板"""

    # 由回测引擎启动（此时将无法获取实时仓位等远端信息）
    inBacktesting = False

    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(CtaTemplate, self).__init__(ctaEngine, setting)

        # 获取回测相关数据
        if 'inBacktesting' in setting:
            self.inBacktesting = setting['inBacktesting']
            if self.inBacktesting:
                self.backtestingDbCache = []
                self.backtestingDbCacheSize = 10000  # TODO 参数化
                self.backtestingDbCacheReachOldest = False

    def onInit(self):
        """初始化策略"""
        # 实盘获取当前仓位
        if not self.inBacktesting:
            # 获取持仓缓存数据
            posBuffer = self.ctaEngine.posBufferDict.get(self.vtSymbol, None)
            if posBuffer:
                self.pos = posBuffer.longPosition - posBuffer.shortPosition
        else:
            self.backtestingDbCacheReachOldest = False

    def sell(self, price, volume, stop=False):
        """卖平"""
        # 实盘上期所需要考虑平今平昨
        if not self.inBacktesting:
            contract = self.ctaEngine.mainEngine.getContract(self.vtSymbol)

            if contract.exchange == EXCHANGE_SHFE:
                # 获取持仓缓存数据
                posBuffer = self.ctaEngine.posBufferDict.get(self.vtSymbol, None)
                # 否则如果有多头今仓，优先平昨
                if posBuffer and posBuffer.longToday > 0:
                    # 计算需要平昨的单数
                    volume_yd = min(posBuffer.longYd, volume)
                    # 保存并清零多头今仓
                    save_longTody = posBuffer.longToday
                    posBuffer.longToday = 0
                    # 在无多头今仓的条件下发单，保证优先平昨
                    vtOrderID_yd = self.sendOrder(CTAORDER_SELL, price, volume_yd, stop)
                    # 还原多头今仓，发送剩下的平今单
                    posBuffer.longToday = save_longTody
                    volume_td = volume - volume_yd
                    vtOrderID_td = self.sendOrder(CTAORDER_SELL, price, volume_td, stop)
                    return (vtOrderID_yd, vtOrderID_td)

        vtOrderID = self.sendOrder(CTAORDER_SELL, price, volume, stop)
        return (vtOrderID,)

    def cover(self, price, volume, stop=False):
        """买平"""
        # 实盘上期所需要考虑平今平昨
        if not self.inBacktesting:
            contract = self.ctaEngine.mainEngine.getContract(self.vtSymbol)

            # 只有上期所才要考虑平今平昨
            if contract.exchange == EXCHANGE_SHFE:
                # 获取持仓缓存数据
                posBuffer = self.ctaEngine.posBufferDict.get(self.vtSymbol, None)
                # 否则如果有空头今仓，优先平昨
                if posBuffer and posBuffer.shortToday > 0:
                    # 计算需要平昨的单数
                    volume_yd = min(posBuffer.shortYd, volume)
                    # 保存并清零空头今仓
                    save_shortToday = posBuffer.shortToday
                    posBuffer.shortToday = 0
                    # 在无空头今仓的条件下发单，保证优先平昨
                    vtOrderID_yd = self.sendOrder(CTAORDER_COVER, price, volume_yd, stop)
                    # 还原空头今仓，发送剩下的平今单
                    posBuffer.shortToday = save_shortToday
                    volume_td = volume - volume_yd
                    vtOrderID_td = self.sendOrder(CTAORDER_COVER, price, volume_td, stop)
                    return (vtOrderID_yd, vtOrderID_td)

        vtOrderID = self.sendOrder(CTAORDER_COVER, price, volume, stop)
        return (vtOrderID,)

    def onTrade(self, trade):
        """收到成交推送"""
        # 实盘存储每笔交易信息
        if not self.inBacktesting:
            self.ctaEngine.insertData(STRATEGY_TRADE_DB_NAME,
                                      '{}_{}'.format(self.className, trade.symbol),
                                      trade.__dict__)

    def getLastKlines(self, count, period=drEngineEx.ctaKLine.PERIOD_1MIN, from_datetime=None,
                      symbol=None, only_completed=True, newest_tick_datetime=None):
        """获取最近的历史K线

        :param count: 获取K线的数量
        :param period: 获取K线的周期
        :param from_datetime: 获取K线的起始时间（向前检索），实盘会忽略该参数；onBar时使用，传K线的datetime
        :param symbol: K线的合约，主要用于指定主力合约代码
        :param only_completed: 只获取已完成的K线，onTick时使用
        :param newest_tick_datetime: 用于精确判定已完成K线，onTick时使用，传tick的datetime
        :return:
        """
        symbol = symbol if symbol else self.vtSymbol.upper()

        # 实盘使用K线生成器获取
        if not self.inBacktesting:
            return self.ctaEngine.mainEngine.drEngine.kline_gen.get_last_klines(
                    symbol, count, period, only_completed, newest_tick_datetime)

        # 非实盘首先尝试从缓存中获取
        idx = bisect.bisect_left(map(lambda b: b.datetime, self.backtestingDbCache), from_datetime)
        if (idx != len(self.backtestingDbCache)
            and self.backtestingDbCache[idx].datetime == from_datetime):
            if idx + 1 - count < 0 and not self.backtestingDbCacheReachOldest:
                pass  # 继续从数据库中获取更前面的数据
            else:
                return self.backtestingDbCache[max(0, idx + 1 - count):idx + 1]

        # 缓存中未找到对应数据则从数据库中获取
        col = self.ctaEngine.dbClient[drEngineEx.ctaKLine.KLINE_DB_NAMES[period]][symbol]
        klines = list(col.find(filter={'datetime': {'$lte': from_datetime}},
                               projection={'_id': False},
                               limit=count,
                               sort=(('date', pymongo.DESCENDING),
                                     ('time', pymongo.DESCENDING))))
        klines.reverse()
        if len(klines) < count:  # 数据库中已无更靠前的数据
            self.backtestingDbCacheReachOldest = True
        # 继续预读
        klinesPreRead = list(col.find(filter={'datetime': {'$gt': from_datetime}},
                                      projection={'_id': False},
                                      limit=self.backtestingDbCacheSize - len(klines),
                                      sort=(('date', pymongo.ASCENDING),
                                            ('time', pymongo.ASCENDING))))
        self.backtestingDbCache = []
        for kline in itertools.chain(klines, klinesPreRead):
            self.backtestingDbCache.append(drEngineEx.ctaKLine.KLine(None))
            self.backtestingDbCache[-1].__dict__.update(kline)
        return self.backtestingDbCache[max(0, len(klines) - count):len(klines)]

    def registerOnbar(self, periods):
        """注册K线回调

        :param periods: 周期集合
        :return:
        """
        # 实盘使用K线生成器注册
        if not self.inBacktesting:
            self.ctaEngine.mainEngine.drEngine.registerKlineCompletedEvent(
                    self.vtSymbol, {period: self.onBar for period in periods})
        else:  # 非实盘直接忽略
            pass

    def unregisterOnbar(self, periods):
        """注销K线回调

        :param periods: 周期集合
        :return:
        """
        # 实盘使用K线生成器注册
        if not self.inBacktesting:
            self.ctaEngine.mainEngine.drEngine.removeKlineCompletedEvent(
                    self.vtSymbol, {period: self.onBar for period in periods})
        else:  # 非实盘直接忽略
            pass
