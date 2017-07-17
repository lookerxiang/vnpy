# encoding: utf-8
import time


def do_everthing(qtApp, mainEngine, mainWindow):
    # 连接数据库
    mainEngine.dbConnect()

    # 连接CTP
    mainEngine.connect('CTP')
    time.sleep(20)

    # 启动策略面板
    mainWindow.signalCta.emit()
    time.sleep(10)

    # 加载策略
    mainWindow.widgetDict['ctaM'].signalLoadAll.emit()
    time.sleep(10)

    # 初始化策略
    mainWindow.widgetDict['ctaM'].signalInitAll.emit()
    time.sleep(10)

    # 启动策略
    mainWindow.widgetDict['ctaM'].signalStartAll.emit()
