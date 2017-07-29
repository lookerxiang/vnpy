import json

import eventType


class MMEngine(object):
    """资金管理引擎"""
    settingFileName = 'MM_setting.json'
    path = os.path.abspath(os.path.dirname(__file__))
    settingFileName = os.path.join(path, settingFileName)

    name = u'资金管理模块'

    def __init__(self, mainEngine, eventEngine):
        """Constructor"""
        self.mainEngine = mainEngine
        self.eventEngine = eventEngine

        # 是否启动资金控制
        self.active = False

        # 设置默认数据库存储位置
        self.db_name = "VnTrader_Account_Db"
        self.col_name = "account"

        # TODO 控制参数
        pass

        self.loadSetting()
        self.registerEvent()

    def loadSetting(self):
        """读取配置"""
        with open(self.settingFileName) as f:
            d = json.load(f)

            # 设置模块参数
            self.active = d['active']
            self.db_name = d['db_name']
            self.col_name = d['col_name']

            # TODO 控制参数
            pass

    def saveSetting(self):
        """保存资金控制参数"""
        with open(self.settingFileName, 'w') as f:
            # 保存模块参数
            d = {}

            d['active'] = self.active
            d['db_name'] = self.db_name
            d['col_name'] = self.col_name

            # 写入json
            jsonD = json.dumps(d, indent=4)
            f.write(jsonD)

    def registerEvent(self):
        """注册事件监听"""
        self.eventEngine.register(eventType.EVENT_ACCOUNT, self.updateAccount)

    def updateAccount(self, event):
        """收到资金更新"""
        account = event.dict_['data']
