# encoding: UTF-8


import datetime as dt
import os
import re
import traceback
from collections import defaultdict
from tkFileDialog import (
    askopenfilename,
    asksaveasfile,
)

import xlrd

FILENAME_SUFFIX = {  # 以秒单位时间差作为字典键
    60     : '_1Min_Db',
    180    : '_3Min_Db',
    300    : '_5Min_Db',
    900    : '_15Min_Db',
    1800   : '_30Min_Db',
    3600   : '_60Min_Db',
    7200   : '_120Min_Db',
    14400  : '_240Min_Db',
    86400  : '_Daily_Db',
    604800 : '_Weekly_Db',
    2419200: '_Monthly_Db',  # 28日
    2505600: '_Monthly_Db',  # 29日
    2592000: '_Monthly_Db',  # 30日
    2678400: '_Monthly_Db',  # 31日
}

DBNAME = {
    '1Min'   : 'VnTrader_1Min_Db',
    '3Min'   : 'VnTrader_3Min_Db',
    '5Min'   : 'VnTrader_5Min_Db',
    '15Min'  : 'VnTrader_15Min_Db',
    '30Min'  : 'VnTrader_30Min_Db',
    '60Min'  : 'VnTrader_60Min_Db',
    '120Min' : 'VnTrader_120Min_Db',
    '240Min' : 'VnTrader_240Min_Db',
    'Daily'  : 'VnTrader_Daily_Db',
    'Weekly' : 'VnTrader_Weekly_Db',
    'Monthly': 'VnTrader_Monthly_Db',
}


def make_csv_files():
    csv_filenames = []
    csv_headers = ("Date", "Time", "Open", "High", "Low", "Close", "TotalVolume")
    datetime_matcher = re.compile(r'\d{4}/\d{2}/\d{2}(-\d{2}:\d{2})?')

    # 前一天夜盘的时间区间，通达信将前一天夜盘的数据日期处理为次日，直接存入会导致K线顺序错乱
    yesterday_start, yesterday_end = dt.time(hour=21), dt.time.max

    workbook = xlrd.open_workbook(askopenfilename(filetypes=[('Excel file', '.xlsx')]))

    for sheet_idx, sheet in enumerate(workbook.sheets()):
        try:
            print('正在读取工作表 {} ...'.format(sheet_idx + 1))

            # 期货名称代号
            code_name = sheet.cell(0, 0)
            print(code_name.value.strip())

            # 寻找第一行数据
            for row_no, cell in enumerate(sheet.col(0)):
                match = datetime_matcher.match(cell.value.strip())
                if match:
                    first_row = row_no
                    datetime_format = '%Y/%m/%d-%H:%M' if match.groups()[0] else '%Y/%m/%d'
                    break
            else:
                raise AssertionError('No data found.')

            # 读取最多前20行数，判断秒间隔
            # 通过取再现次数最多的秒间隔，可以较准确判断
            second_diff_dict = defaultdict(int)
            for row_no in range(first_row, min(first_row + 19, sheet.nrows - 1)):
                datetime_1 = dt.datetime.strptime(sheet.row(row_no)[0].value.strip(), datetime_format)
                datetime_2 = dt.datetime.strptime(sheet.row(row_no + 1)[0].value.strip(), datetime_format)
                next_diff = int((datetime_2 - datetime_1).total_seconds())
                if next_diff > 0:  # 防止时间翻转
                    second_diff_dict[next_diff] += 1
            second_diff = max(zip(second_diff_dict.values(), second_diff_dict.keys()))[1]

            # ！以下方法废除，该方法在30分钟、1小时等K线区间长度不固定的条件下无法正确判断
            # second_diff = max(FILENAME_SUFFIX)
            # for row_no in range(first_row, min(first_row + 9, sheet.nrows - 1)):
            #     datetime_1 = dt.datetime.strptime(sheet.row(row_no)[0].value.strip(), datetime_format)
            #     datetime_2 = dt.datetime.strptime(sheet.row(row_no + 1)[0].value.strip(), datetime_format)
            #     next_diff = int((datetime_2 - datetime_1).total_seconds())
            #     if next_diff > 0:  # 防止时间翻转
            #         second_diff = min(second_diff, next_diff)

            # 打开输出文件
            csv_filename = sheet.name.split('_')[0] + FILENAME_SUFFIX.get(second_diff, '_UNKNOWN_Db')
            with asksaveasfile(initialfile='{}.csv'.format(csv_filename)) as csv_file:
                csv_file.write(','.join(map(repr, csv_headers)).replace('\'', '"') + '\n')

                # 逐行读取数据（前6列）
                line_count = 0
                for row_no in range(first_row, sheet.nrows):
                    row = sheet.row(row_no)

                    datetime = row[0].value.strip()
                    if datetime_matcher.match(datetime):
                        # 分拆日期
                        date = datetime[:10]
                        time = datetime[11:]
                        time += ':00' if time else '00:00:00'

                        # 判定是否是前一日数据
                        if yesterday_start <= dt.time(*map(int, time.split(':'))) <= yesterday_end:
                            yesterday_date = dt.date(*map(int, date.split('/')))
                            while True:  # 寻找前一个工作日
                                yesterday_date -= dt.timedelta(days=1)
                                if yesterday_date.weekday() < 5:
                                    date = yesterday_date.strftime('%Y/%m/%d')
                                    break

                        csv_file.write(','.join([date, time] + map(lambda c: str(c.value), row[1:6])) + '\n')

                        line_count += 1

                csv_filenames.append(csv_file.name)

            print('已完成工作表 {}, 共 {} 行.'.format(sheet_idx + 1, line_count))
        except:
            traceback.print_exc()

    return csv_filenames


def loadMcCsv(fileName, dbName, symbol):
    """将Multicharts导出的csv格式的历史数据插入到Mongo数据库中"""
    import csv, time, pymongo
    from ctaBase import CtaBarData

    start = time.time()
    print u'开始读取CSV文件%s中的数据插入到%s的%s中' % (fileName, dbName, symbol)

    # 锁定集合，并创建索引
    client = pymongo.MongoClient(port=27018)
    collection = client[dbName][symbol]
    collection.ensure_index([('datetime', pymongo.ASCENDING)], unique=True)

    # 读取数据和插入到数据库
    reader = csv.DictReader(file(fileName, 'r'))
    for d in reader:
        bar = CtaBarData()
        bar.vtSymbol = symbol
        bar.symbol = symbol
        bar.open = float(d['Open'])
        bar.high = float(d['High'])
        bar.low = float(d['Low'])
        bar.close = float(d['Close'])
        bar.date = dt.datetime.strptime(d['Date'], '%Y/%m/%d').strftime('%Y%m%d')
        bar.time = d['Time']
        bar.datetime = dt.datetime.strptime(bar.date + ' ' + bar.time, '%Y%m%d %H:%M:%S')
        bar.volume = float(d['TotalVolume'])

        # 记录close_datetime，以便未完成的K线可以继续更新
        bar.__dict__['close_datetime'] = min(dt.datetime.now(), bar.datetime)

        flt = {'datetime': bar.datetime}
        collection.update_one(flt, {'$set': bar.__dict__}, upsert=True)
        print bar.date, bar.time

    print u'插入完毕，耗时：%s' % (time.time() - start)


def load_csv_files(filenames):
    for name in filenames:
        try:
            symbol, time, _ = os.path.basename(name).split('_')
            loadMcCsv(name, DBNAME[time], symbol)
        except:
            traceback.print_exc()


if __name__ == '__main__':
    csv_filenames = make_csv_files()
    load_csv_files(csv_filenames)
