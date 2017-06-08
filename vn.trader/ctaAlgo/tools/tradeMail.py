# encoding: UTF-8

'''
本文件中包含的是CTA模块的回测引擎，回测引擎的API和CTA引擎一致，
可以使用和实盘相同的代码进行回测。
'''

import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
import json
import os

class Mail(object):
    fileName = 'mailAuthCode.json'

    name = u'mailAuthCode'
    # ----------------------------------------------------------------------
    def __init__(self):
        """Constructor"""
        self.sender = ''  # 发件人
        self.password = ''  # 授权码
        self.toList = ''  # 收件人列表
        self.loadSetting()


    def sendMail(self,toList,sub,content):

        try:
            msg=MIMEText(content,'plain','utf-8')
            msg['From']=formataddr(["FromVnpy",self.sender])  # 括号里的对应发件人邮箱昵称、发件人邮箱账号
            msg['To'] = ";".join(toList)  # 括号里的对应收件人邮箱昵称、收件人邮箱账号
            msg['Subject']=sub                # 邮件的主题，也可以说是标题

            server=smtplib.SMTP_SSL("smtp.qq.com", 465)  # 发件人邮箱中的SMTP服务器，端口是25
            server.login(self.sender, self.password)  # 括号中对应的是发件人邮箱账号、邮箱密码
            server.sendmail(self.sender,toList,msg.as_string())  # 括号中对应的是发件人邮箱账号、收件人邮箱账号、发送邮件
            server.quit()  # 关闭连接
            return True
        except Exception as e:  # 如果 try 中的语句没有执行，则会执行下面的 ret=False
            print str(e)
            # ret=False
            return False
    #----------------------------------------------------------------------
    def loadSetting(self):
        """载入配置"""
        try:
            path = os.path.abspath(os.path.dirname(__file__))
            fileName = os.path.join(path, self.fileName)
            f = file(fileName)
        except IOError:
            print u'%s无法打开配置文件' % self.name
            return

        setting = json.load(f)
        try:
            self.sender = setting['sender']
            self.password = setting['password']
            self.toList = setting['toList']
        except KeyError:
            print u'%s配置文件字段缺失' % self.name
            return

        print u'%s配置载入完成' % self.name

if __name__ == '__main__':
    # sender = '247073858@qq.com'  # 发件人邮箱账号
    # password = 'XXXXXXX'  # 发件人邮箱密码
    # toList = ['247073858@qq.com']  # 收件人邮箱账号，我这边发送给自己
    test=Mail()
    if test.sendMail(test.toList,"hello","hello world！"):
        print "发送成功"
    else:
        print "发送失败"

