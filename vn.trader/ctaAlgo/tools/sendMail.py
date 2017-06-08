# encoding: UTF-8

'''
本文件中包含的是CTA模块的回测引擎，回测引擎的API和CTA引擎一致，
可以使用和实盘相同的代码进行回测。
'''

import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr


def mail(to_list,sub,content):
    # ret=True

    try:
        msg=MIMEText(content,'plain','utf-8')
        msg['From']=formataddr(["FromRunoob",my_sender])  # 括号里的对应发件人邮箱昵称、发件人邮箱账号
        msg['To'] = ";".join(to_list)  # 括号里的对应收件人邮箱昵称、收件人邮箱账号
        msg['Subject']=sub                # 邮件的主题，也可以说是标题

        server=smtplib.SMTP_SSL("smtp.qq.com", 465)  # 发件人邮箱中的SMTP服务器，端口是25
        server.login(my_sender, my_pass)  # 括号中对应的是发件人邮箱账号、邮箱密码
        server.sendmail(my_sender,to_list,msg.as_string())  # 括号中对应的是发件人邮箱账号、收件人邮箱账号、发送邮件
        server.quit()  # 关闭连接
        return True
    except Exception as e:  # 如果 try 中的语句没有执行，则会执行下面的 ret=False
        print str(e)
        # ret=False
        return False

if __name__ == '__main__':
    my_sender = '247073858@qq.com'  # 发件人邮箱账号
    my_pass = 'XXXXXXX'  # 发件人邮箱密码

    to_list = ['247073858@qq.com']  # 收件人邮箱账号，我这边发送给自己

    if mail(to_list,"hello","hello world！"):
        print "发送成功"
    else:
        print "发送失败"

