# encoding: UTF-8

'''
在原生ctaBacktesting基础上定制自己的回测系统：
1、显示均线等
2、实现多周期。
'''
from ctaAlgo.ctaBacktesting import *
import numpy as np
import pandas as pd
from math import floor
import matplotlib
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from operator import itemgetter, attrgetter
import os
import xlrd
from xlwt import Workbook
# import xlwt

########################################################################
class BacktestingEngineEx(BacktestingEngine):
    # ----------------------------------------------------------------------
    def __init__(self):
        super(BacktestingEngineEx, self).__init__()

        #self.period = [5, 12]  # k线周期，默认为5和12
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
    def calculateBacktestingResult(self):
        """
        计算回测结果
        """
        self.output(u'计算回测结果')

        # 首先基于回测后的成交记录，计算每笔交易的盈亏
        resultList = []  # 交易结果列表

        longTrade = []  # 未平仓的多头交易
        shortTrade = []  # 未平仓的空头交易

        for trade in self.tradeDict.values():
            # 多头交易
            if trade.direction == DIRECTION_LONG:
                # 如果尚无空头交易
                if not shortTrade:
                    longTrade.append(trade)
                # 当前多头交易为平空
                else:
                    while True:
                        entryTrade = shortTrade[0]
                        exitTrade = trade

                        # 清算开平仓交易
                        closedVolume = min(exitTrade.volume, entryTrade.volume)
                        result = TradingResult(entryTrade.price, entryTrade.dt,
                                               exitTrade.price, exitTrade.dt,
                                               -closedVolume, self.rate, self.slippage, self.size)
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

        maxContinueDrawdownNumber = 0  # 最长连续回撤次数
        continueDrawdownNumberList = []  # 连续回撤次数列表
        maxContinueDrawdownTime = 0  # 最长连续回撤时间
        continueDrawdownTimeList = []  # 连续回撤时间列表

        
        drawdownCount = 0

        


        winningResult = 0  # 盈利次数
        losingResult = 0  # 亏损次数
        totalWinning = 0  # 总盈利金额
        totalLosing = 0  # 总亏损金额

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

            #计算最大连续回测次数和时间
            if result.pnl < 0:
                drawdownCount += 1
                if drawdownCount == 1:
                    maxContinueDrawdownStartTime = result.entryDt
                maxContinueDrawdownEndTime = result.exitDt
                tempTime = maxContinueDrawdownEndTime - maxContinueDrawdownStartTime
                tempNumber = drawdownCount

                if totalResult == len(resultList) and drawdownCount == 1:#最后一个为负，且倒数第二个为正
                    continueDrawdownTimeList.append(result.exitDt - result.entryDt)
                    continueDrawdownNumberList.append(1)
            else:
                if drawdownCount >= 1:
                    continueDrawdownTimeList.append(tempTime)
                    continueDrawdownNumberList.append(tempNumber)
                drawdownCount = 0
        # 计算盈亏相关数据
        winningRate = floor(winningResult) / totalResult * 100.0  # 胜率

        averageWinning = 0  # 这里把数据都初始化为0
        averageLosing = 0
        profitLossRatio = 0

        if winningResult:
            averageWinning = totalWinning / winningResult  # 平均每笔盈利
        if losingResult:
            averageLosing = totalLosing / losingResult  # 平均每笔亏损
        if averageLosing:
            profitLossRatio = -averageWinning / averageLosing  # 盈亏比

        maxContinueDrawdownNumber = max(continueDrawdownNumberList)
        maxContinueDrawdownTime=max(continueDrawdownTimeList)
        # 返回回测结果
        d = {}
        d['capital'] = capital
        d['maxCapital'] = maxCapital
        d['drawdown'] = drawdown
        d['totalResult'] = totalResult
        d['totalTurnover'] = totalTurnover
        d['totalCommission'] = totalCommission
        d['totalSlippage'] = totalSlippage
        d['timeList'] = timeList
        d['pnlList'] = pnlList
        d['capitalList'] = capitalList
        d['drawdownList'] = drawdownList
        d['winningRate'] = winningRate
        d['averageWinning'] = averageWinning
        d['averageLosing'] = averageLosing
        d['profitLossRatio'] = profitLossRatio
        d['maxContinueDrawdownNumber'] = maxContinueDrawdownNumber
        d['maxContinueDrawdownTime'] = maxContinueDrawdownTime


        return d


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
        self.output(u'最大连续回撤次数：\t%s' % d['maxContinueDrawdownNumber'])
        self.output(u'最大连续回撤时间：\t%s' % d['maxContinueDrawdownTime'])

        # 输出到文件
        self.output(u'输出优化结果到文件中：')
        path = os.path.abspath(os.path.join(os.getcwd(), "..")) + '/strategyAnalysis/' + '/'
        if not os.path.exists(path):
            dir = os.makedirs(path)
        # fileName =os.path.join(path,str(self.strategy.className)+' '+str(self.symbol)+' '+str(self.startDate)+"-"+str(self.endDate)+'.txt')
        # f = open(fileName,'w')
        # for result in resultList:
        #     self.outFile(f,u'%s: %s' % (result[0], result[1]))
        # f.close()
        now = datetime.now()
        nowstr = str(now.year) + '-' + str(now.month) + '-' + str(now.day) + '-' + str(now.hour) + '-' + str(
            now.minute) + '-' + str(now.second)
        fileName = os.path.join(path, str(self.strategy.className) + ' ' + str(self.symbol) + ' ' + str(
            self.startDate) + "-" + str(self.endDate) + ' ' + nowstr + '.xls')
        book = Workbook()  # 将内置函数Workbook赋值给book
        sheet = book.add_sheet(u'优化结果')  # 给新建excel添加sheet


        # 标题栏


        nameList = self.strategy.paramList
        i = 0
        for key in nameList:
            sheet.write(0, i, key)
            sheet.write(1, i, self.strategy.__dict__[key])
            i += 1
        lenParm=len(nameList)
        sheet.write(0, lenParm, u'第一笔交易')
        sheet.write(0, lenParm+1, u'最后一笔交易')
        sheet.write(0, lenParm+2, u'总交易次数')
        sheet.write(0, lenParm+3, u'总盈亏')
        sheet.write(0, lenParm+4, u'最大回撤')
        sheet.write(0, lenParm+5, u'平均每笔盈利')
        sheet.write(0, lenParm+6, u'平均每笔滑点')
        sheet.write(0, lenParm+7, u'平均每笔佣金')
        sheet.write(0, lenParm+8, u'胜率')
        sheet.write(0, lenParm+9, u'盈利交易平均值')
        sheet.write(0, lenParm+10, u'盈亏比')
        sheet.write(0, lenParm+11, u'最大连续回撤次数')
        sheet.write(0, lenParm+12, u'最大连续回撤时间')

        sheet.write(1, lenParm, d['timeList'][0])
        sheet.write(1, lenParm + 1, d['timeList'][-1])
        sheet.write(1, lenParm + 2, formatNumber(d['totalResult']))
        sheet.write(1, lenParm + 3, formatNumber(d['capital']))
        sheet.write(1, lenParm + 4, formatNumber(min(d['drawdownList'])))
        sheet.write(1, lenParm + 5, formatNumber(d['capital'] / d['totalResult']))
        sheet.write(1, lenParm + 6, formatNumber(d['totalSlippage'] / d['totalResult']))
        sheet.write(1, lenParm + 7, formatNumber(d['totalCommission'] / d['totalResult']))
        sheet.write(1, lenParm + 8, formatNumber(d['winningRate']))
        sheet.write(1, lenParm + 9, formatNumber(d['averageWinning']))
        sheet.write(1, lenParm + 10, formatNumber(d['profitLossRatio']))
        sheet.write(1, lenParm + 11, str(d['maxContinueDrawdownNumber']))
        sheet.write(1, lenParm + 12, str(d['maxContinueDrawdownTime']))

        book.save(fileName)  # 保存excel到新excel

        self.output(u'输出优化结果到文件中完成！！！')

        # 绘图
        # import matplotlib
        # matplotlib.use('TkAgg')
        # import matplotlib.pyplot as plt

        fig = plt.figure(1)
        pCapital = plt.subplot(3, 1, 1)
        pCapital.set_ylabel("capital")
        pCapital.plot(d['timeList'], d['capitalList'])
        #画资金曲线的移动平均线
        ts = pd.Series(d['capitalList'], index=pd.DatetimeIndex(d['timeList']))
        ts.rolling(window=20, win_type='boxcar').mean().plot()

        pDD = plt.subplot(3, 1, 2)
        pDD.set_ylabel("DD")  # 最大回撤
        pDD.bar(d['timeList'], d['drawdownList'])

        pPnl = plt.subplot(3, 1, 3)
        pPnl.set_ylabel("pnl")  # 净盈亏序列
        pPnl.hist(d['pnlList'], bins=150)

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
        tradeplot.plot(timedata, closedata, 'y', marker='.',label="close price")
        tradeplot.plot(longtime, longprice, 'r^', label="duo")  #
        tradeplot.plot(shorttime, shortprice, 'gv', label='kong')
        tradeplot.plot(closetime, closeprice, 'ko', label='no')

        ts = pd.Series(closedata, index=pd.DatetimeIndex(timedata))
        # pd.rolling_mean(ts ,self.period).plot()
        # if isinstance(self.period, list):  #如果是列表则循环
        #     for prd in self.period:
        #         ts.rolling(window=prd, win_type='boxcar').mean().plot()
        # else:                              #否则
        #     ts.rolling(window=self.period, win_type='boxcar').mean().plot()

        if hasattr(self.strategy, 'shortPeriod'):
            ts.rolling(window=self.strategy.shortPeriod, win_type='boxcar').mean().plot()
        if hasattr(self.strategy, 'middlePeriod'):
            ts.rolling(window=self.strategy.middlePeriod, win_type='boxcar').mean().plot()
        if hasattr(self.strategy, 'longPeriod'):
            ts.rolling(window=self.strategy.longPeriod, win_type='boxcar').mean().plot()



        tradeplot.legend(loc='best')
        plt.grid(True)
        plt.show()

    # ----------------------------------------------------------------------
    def runParallelOptimization(self, strategyClass, optimizationSetting):
        """并行优化参数"""
        # 获取优化设置
        settingList = optimizationSetting.generateSetting()
        targetName = optimizationSetting.optimizeTarget

        # 检查参数设置问题
        if not settingList or not targetName:
            self.output(u'优化设置有问题，请检查')

        # 多进程优化，启动一个对应CPU核心数量的进程池
        pool = multiprocessing.Pool(multiprocessing.cpu_count())
        l = []

        for setting in settingList:
            l.append(pool.apply_async(optimize, (strategyClass, setting,
                                                 targetName, self.mode,
                                                 self.startDate, self.initDays, self.endDate,
                                                 self.slippage, self.rate, self.size,
                                                 self.dbName, self.symbol)))
        pool.close()
        pool.join()

        # 显示结果
        resultList = [res.get() for res in l]
        resultList.sort(reverse=True, key=lambda result: result[1])
        self.output('-' * 30)
        self.output(u'优化结果：')
        for result in resultList:
            self.output(u'%s: %s' % (result[0], result[1]))

        #输出优化结果到文件中
        self.output(u'输出优化结果到文件中：')
        path =  os.path.abspath(os.path.join(os.getcwd(), "..")) + '/strategyAnalysis/' +  '/'
        if not os.path.exists(path):
            dir=os.makedirs(path)
        # fileName =os.path.join(path,str(self.strategy.className)+' '+str(self.symbol)+' '+str(self.startDate)+"-"+str(self.endDate)+'.txt')
        # f = open(fileName,'w')
        # for result in resultList:
        #     self.outFile(f,u'%s: %s' % (result[0], result[1]))
        # f.close()
        now = datetime.now()
        nowstr=str(now.year)+ '-'+str(now.month)+ '-'+str(now.day)+'-'+str(now.hour)+ '-'+str(now.minute)+ '-'+str(now.second)
        fileName =os.path.join(path,str(self.strategy.className)+' '+str(self.symbol)+' '+str(self.startDate)+"-"+str(self.endDate)+' Optimization'+' '+nowstr+'.xls')
        book = Workbook()  # 将内置函数Workbook赋值给book
        sheet=book.add_sheet(u'优化结果')  # 给新建excel添加sheet
        #标题栏
        nameList = optimizationSetting.paramDict.keys()
        i=0
        for name in eval(resultList[0][0]).keys():
            sheet.write(0,i,name)
            i+=1
        sheet.write(0, len(nameList), targetName)

        j=0
        for result in resultList:
            i = 0
            j+=1
            for value in eval(result[0]).values():
                sheet.write(j, i, value)
                i+=1
            sheet.write(j, i, result[1])

        book.save(fileName)  # 保存excel到新excel

        self.output(u'输出优化结果到文件中完成！！！')

        return resultList
    # 绘制三维曲面图----------------------------------------------------------------------------------------------------
    def runSurface(self, parm1,parm2, resultList):
        """画三维曲面图"""
        x=[]
        y=[]
        z=[]
        # resultListSorted=sorted(resultList, key=itemgetter(1,2))
        for result in resultList:
            x.append(eval(result[0])[parm1])
            y.append(eval(result[0])[parm2])
            z.append(result[1])

        # X, Y, Z = np.meshgrid(np.array(x), np.array(y), np.array(z))
        x = np.array(x)
        y = np.array(y)
        z = np.array(z)
        xyz=zip(x,y,z)
        xyzSorted=sorted(xyz, key=itemgetter(0, 1))
        xset=sorted(set(x))
        yset=sorted(set(y))
        # X,Y=np.meshgrid(xset,yset)
        X=np.empty((len(xset),len(yset)))
        Y=np.empty((len(xset),len(yset)))
        Z=np.empty((len(xset),len(yset)))
        for i in range(len(xset)):
            for j in range(len(yset)):
                # X[i][j]=x[i*len(yset)+j]
                # Y[i][j]=y[i*len(yset)+j]
                X[i][j]=xyzSorted[i*len(yset)+j][0]
                Y[i][j]=xyzSorted[i*len(yset)+j][1]
                Z[i][j]=xyzSorted[i*len(yset)+j][2]

        fig = plt.figure()
        ax = Axes3D(fig)
        # 具体函数方法可用 help(function) 查看，如：help(ax.plot_surface)
        ax.plot_surface(X, Y, Z, rstride=1, cstride=1, cmap='rainbow')
        ax.set_zlabel('capital')  # 坐标轴
        ax.set_ylabel(parm2)
        ax.set_xlabel(parm1)
        plt.show()



    # ----------------------------------------------------------------------
    def outFile(self, file, content):
        """输出内容到文件"""
        print >> file, str(datetime.now()) + "\t" + content


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
    
    