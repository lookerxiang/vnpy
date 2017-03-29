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
    def __int__(self):
        super(CtaTemplate, self).__init__(self)

        self.period = [5, 12]  # k线周期，默认为5和12
        self.backtestingData = []   # 回测用的数据

    # ----------------------------------------------------------------------
    def setStartDate(self, startDate='20150416', initDays=10):
        """设置回测的启动日期"""
        self.startDate = startDate
        self.initDays = initDays
        self.dataStartDate = datetime.strptime(startDate, '%Y%m%d')  # 数据开始时间
        initTimeDelta = timedelta(initDays)
        self.strategyStartDate = self.dataStartDate + initTimeDelta  # 策略开始时间，即前面的数据用于初始化
        self.strategy.onInitDays(self.initDays)

    # ----------------------------------------------------------------------
    def loadHistoryData(self):
        """载入历史数据"""
        host, port = loadMongoSetting()

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
    def crossLimitOrder(self):
        """基于最新数据撮合限价单"""
        # 先确定会撮合成交的价格
        if self.mode == self.BAR_MODE:
            buyCrossPrice = self.bar.low  # 若买入方向限价单价格高于该价格，则会成交
            sellCrossPrice = self.bar.high  # 若卖出方向限价单价格低于该价格，则会成交
            buyBestCrossPrice = self.bar.open  # 在当前时间点前发出的买入委托可能的最优成交价
            sellBestCrossPrice = self.bar.open  # 在当前时间点前发出的卖出委托可能的最优成交价
        else:
            buyCrossPrice = self.tick.askPrice1
            sellCrossPrice = self.tick.bidPrice1
            buyBestCrossPrice = self.tick.askPrice1
            sellBestCrossPrice = self.tick.bidPrice1

        # 遍历限价单字典中的所有限价单
        for orderID, order in self.workingLimitOrderDict.items():
            # 判断是否会成交
            buyCross = order.direction == DIRECTION_LONG and order.price >= buyCrossPrice
            sellCross = order.direction == DIRECTION_SHORT and order.price <= sellCrossPrice

            # 如果发生了成交
            if buyCross or sellCross:
                # 推送成交数据
                self.tradeCount += 1  # 成交编号自增1
                tradeID = str(self.tradeCount)
                trade = VtTradeData()
                trade.vtSymbol = order.vtSymbol
                trade.tradeID = tradeID
                trade.vtTradeID = tradeID
                trade.orderID = order.orderID
                trade.vtOrderID = order.orderID
                trade.direction = order.direction
                trade.offset = order.offset

                # 以买入为例：
                # 1. 假设当根K线的OHLC分别为：100, 125, 90, 110
                # 2. 假设在上一根K线结束(也是当前K线开始)的时刻，策略发出的委托为限价105
                # 3. 则在实际中的成交价会是100而不是105，因为委托发出时市场的最优价格是100
                if buyCross:
                    trade.price = min(order.price, buyBestCrossPrice)
                    self.strategy.pos += order.totalVolume
                else:
                    trade.price = max(order.price, sellBestCrossPrice)
                    self.strategy.pos -= order.totalVolume

                trade.volume = order.totalVolume
                trade.tradeTime = str(self.dt)
                trade.dt = self.dt
                self.strategy.onTrade(trade)

                self.tradeDict[tradeID] = trade

                # 推送委托数据
                order.tradedVolume = order.totalVolume
                order.status = STATUS_ALLTRADED
                # self.strategy.onOrder(order) #该处只有成交了才回调策略，应该成交与否都回调，所以改在if外边
                # 从字典中删除该限价单
                del self.workingLimitOrderDict[orderID]
                # print trade.tradeTime, self.strategy.pos
                # print  self.strategy.pos
            self.strategy.onOrder(order)  # 回调函数，传给策略交易状态
            # print order.orderTime, "Limit", order.status, self.strategy.pos
            # ----------------------------------------------------------------------

    def crossStopOrder(self):
        """基于最新数据撮合停止单"""
        # 先确定会撮合成交的价格，这里和限价单规则相反
        if self.mode == self.BAR_MODE:
            buyCrossPrice = self.bar.high  # 若买入方向停止单价格低于该价格，则会成交。说明多头止损单被触发了
            sellCrossPrice = self.bar.low  # 若卖出方向限价单价格高于该价格，则会成交。说明空头止损单被触发了
            bestCrossPrice = self.bar.open  # 最优成交价，买入停止单不能低于，卖出停止单不能高于
        else:
            buyCrossPrice = self.tick.lastPrice
            sellCrossPrice = self.tick.lastPrice
            bestCrossPrice = self.tick.lastPrice

        # 遍历停止单字典中的所有停止单
        for stopOrderID, so in self.workingStopOrderDict.items():
            # 判断是否会成交
            buyCross = so.direction == DIRECTION_LONG and so.price <= buyCrossPrice
            sellCross = so.direction == DIRECTION_SHORT and so.price >= sellCrossPrice

            # 如果发生了成交
            if buyCross or sellCross:
                # 推送成交数据
                self.tradeCount += 1  # 成交编号自增1
                tradeID = str(self.tradeCount)
                trade = VtTradeData()
                trade.vtSymbol = so.vtSymbol
                trade.tradeID = tradeID
                trade.vtTradeID = tradeID

                if buyCross:
                    self.strategy.pos += so.volume
                    trade.price = max(bestCrossPrice, so.price)
                else:
                    self.strategy.pos -= so.volume
                    trade.price = min(bestCrossPrice, so.price)

                self.limitOrderCount += 1
                orderID = str(self.limitOrderCount)
                trade.orderID = orderID
                trade.vtOrderID = orderID

                trade.direction = so.direction
                trade.offset = so.offset
                trade.volume = so.volume
                trade.tradeTime = str(self.dt)
                trade.dt = self.dt
                self.strategy.onTrade(trade)

                self.tradeDict[tradeID] = trade

                # 推送委托数据
                so.status = STOPORDER_TRIGGERED

                order = VtOrderData()
                order.vtSymbol = so.vtSymbol
                order.symbol = so.vtSymbol
                order.orderID = orderID
                order.vtOrderID = orderID
                order.direction = so.direction
                order.offset = so.offset
                order.price = so.price
                order.totalVolume = so.volume
                order.tradedVolume = so.volume
                order.status = STATUS_ALLTRADED
                order.orderTime = trade.tradeTime
                self.strategy.onOrder(order)

                self.limitOrderDict[orderID] = order

                # 从字典中删除该限价单
                if stopOrderID in self.workingStopOrderDict:
                    del self.workingStopOrderDict[stopOrderID]
            else:  # 未成交用于未成交的的止损单的状态回调，便于在策略中撤掉未成交的单
                order = VtOrderData()
                order.vtOrderID = stopOrderID
                order.orderTime = str(self.dt)
                order.status = so.status
                self.strategy.onOrder(order)  # 回调函数，传给策略交易状态


    def calculateBacktestingResult(self):
        """
        计算回测结果
        """
        self.output(u'计算回测结果')

        # 首先基于回测后的成交记录，计算每笔交易的盈亏
        resultList = []  # 交易结果列表

        longTrade = []  # 未平仓的多头交易
        shortTrade = []  # 未平仓的空头交易
        longtime = []  # 开多仓时间
        longprice = []  # 开多仓价格
        shorttime = []  # 开空仓时间
        shortprice = []  # 空仓价格
        closetime = []
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

        for trade in self.tradeDict.values():
            # 多头交易
            if trade.direction == DIRECTION_LONG:
                # 如果尚无空头交易，即开多仓
                if not shortTrade:
                    longTrade.append(trade)
                    longtime.append(trade.tradeTime)
                    longprice.append(trade.price)

                # 当前多头交易为平空，平多仓
                else:
                    while True:
                        entryTrade = shortTrade[0]
                        exitTrade = trade

                        # 清算开平仓交易
                        closedVolume = min(exitTrade.volume, entryTrade.volume)

                        result = TradingResult(entryTrade.price, entryTrade.dt,
                                               exitTrade.price, exitTrade.dt,
                                               closedVolume, self.rate, self.slippage, self.size)
                        resultList.append(result)

                        # 计算未清算部分
                        entryTrade.volume -= closedVolume
                        exitTrade.volume -= closedVolume

                        # 如果开仓交易已经全部清算，则从列表中移除
                        if not entryTrade.volume:
                            shortTrade.pop(0)

                        # 如果平仓交易已经全部清算，则退出循环
                        if not exitTrade.volume:
                            break

                        # 如果平仓交易未全部清算，
                        if exitTrade.volume:
                            # 且开仓交易已经全部清算完，则平仓交易剩余的部分
                            # 等于新的反向开仓交易，添加到队列中
                            if not shortTrade:
                                longTrade.append(exitTrade)
                                break
                            # 如果开仓交易还有剩余，则进入下一轮循环
                            else:
                                pass

            # 空头交易
            else:
                # 如果尚无多头交易
                if not longTrade:
                    shortTrade.append(trade)
                    shorttime.append(trade.tradeTime)
                    shortprice.append(trade.price)
                # 当前空头交易为平多
                else:
                    while True:
                        entryTrade = longTrade[0]
                        exitTrade = trade

                        # 清算开平仓交易
                        closedVolume = min(exitTrade.volume, entryTrade.volume)

                        result = TradingResult(entryTrade.price, entryTrade.dt,
                                               exitTrade.price, exitTrade.dt,
                                               closedVolume, self.rate, self.slippage, self.size)
                        resultList.append(result)

                        # 计算未清算部分
                        entryTrade.volume -= closedVolume
                        exitTrade.volume -= closedVolume

                        # 如果开仓交易已经全部清算，则从列表中移除
                        if not entryTrade.volume:
                            longTrade.pop(0)

                        # 如果平仓交易已经全部清算，则退出循环
                        if not exitTrade.volume:
                            break

                        # 如果平仓交易未全部清算，
                        if exitTrade.volume:
                            # 且开仓交易已经全部清算完，则平仓交易剩余的部分
                            # 等于新的反向开仓交易，添加到队列中
                            if not longTrade:
                                shortTrade.append(exitTrade)
                                break
                            # 如果开仓交易还有剩余，则进入下一轮循环
                            else:
                                pass

                                # 检查是否有交易
        if not resultList:
            self.output(u'无交易结果')
            return {}

        # 然后基于每笔交易的结果，我们可以计算具体的盈亏曲线和最大回撤等
        capital = 0  # 资金
        maxCapital = 0  # 资金最高净值
        drawdown = 0  # 回撤

        totalResult = 0  # 总成交数量
        totalTurnover = 0  # 总成交金额（合约面值）
        totalCommission = 0  # 总手续费
        totalSlippage = 0  # 总滑点
        timeList = []  # 时间序列

        pnlList = []  # 每笔盈亏序列
        capitalList = []  # 盈亏汇总的时间序列
        drawdownList = []  # 回撤的时间序列

        winningResult = 0  # 盈利次数
        losingResult = 0  # 亏损次数
        totalWinning = 0  # 总盈利金额
        totalLosing = 0  # 总亏损金额

        # 画图所学要的列表  #平仓再说
        openmultitime = []
        openmultiprice = []
        openshorttime = []
        openshortprice = []

        for result in resultList:
            capital += result.pnl
            maxCapital = max(capital, maxCapital)
            drawdown = capital - maxCapital

            pnlList.append(result.pnl)
            timeList.append(result.exitDt)  # 交易的时间戳使用平仓时间
            capitalList.append(capital)
            drawdownList.append(drawdown)

            totalResult += 1
            totalTurnover += result.turnover
            totalCommission += result.commission
            totalSlippage += result.slippage

            if result.pnl >= 0:
                winningResult += 1
                totalWinning += result.pnl
            else:
                losingResult += 1
                totalLosing += result.pnl

            # 从result中调取需要的画图列表
            if result.entryDirec == u'多':
                openmultiprice.append(result.entryPrice)
                openmultitime.append(result.entryDt)

            elif result.entryDirec == u'空':
                openshortprice.append(result.entryPrice)
                openshorttime.append(result.entryDt)

        # 计算盈亏相关数据
        winningRate = winningResult / totalResult * 100  # 胜率

        averageWinning = 0  # 这里把数据都初始化为0
        averageLosing = 0
        profitLossRatio = 0

        if winningResult:
            averageWinning = totalWinning / winningResult  # 平均每笔盈利
        if losingResult:
            averageLosing = totalLosing / losingResult  # 平均每笔亏损
        if averageLosing:
            profitLossRatio = -averageWinning / averageLosing  # 盈亏比

        # 返回回测结果
        d = {}
        d['capital'] = capital
        d['maxCapital'] = maxCapital
        d['drawdown'] = drawdown
        d['totalResult'] = totalResult
        d['totalTurnover'] = totalTurnover
        d['totalCommission'] = totalCommission
        d['totalSlippage'] = totalSlippage
        d['timeList'] = timeList  # 平仓时间
        d['pnlList'] = pnlList
        d['capitalList'] = capitalList
        d['drawdownList'] = drawdownList
        d['winningRate'] = winningRate
        d['averageWinning'] = averageWinning
        d['averageLosing'] = averageLosing
        d['profitLossRatio'] = profitLossRatio
        # 画图需要的东西
        d['openmultitime'] = openmultitime
        d['openmultiprice'] = openmultiprice
        d['openshorttime'] = openshorttime
        d['openshortprice'] = openshortprice
        d['closetime'] = closetime
        d['closeprice'] = closeprice
        d['longtime'] = longtime
        d['longprice'] = longprice
        d['shorttime'] = shorttime
        d['shortprice'] = shortprice

        return d, resultList

    # ----------------------------------------------------------------------
    def showBacktestingResult(self):
        """显示回测结果"""
        d, resultList = self.calculateBacktestingResult()

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
        tradeplot.plot(d['longtime'], d['longprice'], 'r^', label="duo")  #
        tradeplot.plot(d['shorttime'], d['shortprice'], 'g^', label='kong')
        tradeplot.plot(d['closetime'], d['closeprice'], 'ko', label='no')

        ts = pd.Series(closedata, index=pd.DatetimeIndex(timedata))
        # pd.rolling_mean(ts ,self.period).plot()
        if isinstance(self.period, list):
            for prd in self.period:
                ts.rolling(window=prd, win_type='boxcar').mean().plot()
        else:
            ts.rolling(window=self.period, win_type='boxcar').mean().plot()

        tradeplot.legend(loc='best')

        #




        # xlk自己修改
        # plt.show()
        #   for temp in self.backtestingData:
        #   fig2 = plt.figure(2)
        #   ax2=fig2.add_subplot(1,1,1)
        #   ax2.plot(closeData)
        #   ax2.plot(d['timeList'],color='g',linestyle='dashed',marker='o')
        # ax2.set_ylabel("收盘价")

        plt.show()

    # ----------------------------------------------------------------------
    def setMaPeriod(self, period):
        """设置均线周期"""
        self.period = period  # 将周期赋值给BacktestingEngine类的实例的属性self.period
        self.strategy.onMaPeriod(self.period)  # 并将其回调给strategy。目的是使得二者的周期Ma一致

    # ----------------------------------------------------------------------
    def runOptimization(self, strategyClass, optimizationSetting):
        """优化参数"""
        # 获取优化设置
        settingList = optimizationSetting.generateSetting()
        targetName = optimizationSetting.optimizeTarget

        # 检查参数设置问题
        if not settingList or not targetName:
            self.output(u'优化设置有问题，请检查')

        # 遍历优化
        resultList = []
        for setting in settingList:
            self.clearBacktestingResult()
            self.output('-' * 30)
            self.output('setting: %s' % str(setting))
            self.initStrategy(strategyClass, setting)
            self.runBacktesting()
            d, rslt = self.calculateBacktestingResult()
            try:
                targetValue = d[targetName]
            except KeyError:
                targetValue = 0
            resultList.append(([str(setting)], targetValue))

        # 显示结果
        resultList.sort(reverse=True, key=lambda result: result[1])
        self.output('-' * 30)
        self.output(u'优化结果：')
        for result in resultList:
            self.output(u'%s: %s' % (result[0], result[1]))
        return result


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
    
    