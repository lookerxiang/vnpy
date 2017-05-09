# encoding: UTF-8

import copy
import datetime as dt
import random

import pymongo

import dataRecorder.drEngineEx.ctaKLine as ctakline


def generate(period,
             history_start_date, history_end_date, history_collection,
             gen_start_date, gen_end_date, gen_collection):
    """随机生成K线数据
    
    :param period:              K线周期，指定 dataRecorder.drEngineEx.ctaKLine 中定义的值
    :param history_start_date:  历史K线数据开始日期 YYYYMMDD
    :param history_end_date:    历史K线数据结束日期 YYYYMMDD
    :param history_collection:  历史K线数据文档名
    :param gen_start_date:      生成K线起始日期
    :param gen_end_date:        生成K线结束日期
    :param gen_collection:      生成K线数据文档名
    :return: 
    """
    history_start_datetime = dt.datetime.combine(
            dt.date(int(history_start_date[:4]),
                    int(history_start_date[4:6]),
                    int(history_start_date[-2:])),
            dt.time.min)
    history_end_datetime = dt.datetime.combine(
            dt.date(int(history_end_date[:4]),
                    int(history_end_date[4:6]),
                    int(history_end_date[-2:])),
            dt.time.max)
    start_datetime = dt.datetime.combine(
            dt.date(int(gen_start_date[:4]),
                    int(gen_start_date[4:6]),
                    int(gen_start_date[-2:])),
            dt.time.min)
    end_datetime = dt.datetime.combine(
            dt.date(int(gen_end_date[:4]),
                    int(gen_end_date[4:6]),
                    int(gen_end_date[-2:])),
            dt.time.max)

    db_client = pymongo.MongoClient()

    history_datas = []
    for kline in db_client[ctakline.KLINE_DB_NAMES[period]][history_collection].find(
            filter={'datetime': {'$gte': history_start_datetime,
                                 '$lte': history_end_datetime}},
            projection={'_id': False},
            sort=(('datetime', pymongo.ASCENDING),)):
        history_datas.append(ctakline.KLine(None))
        history_datas[-1].__dict__.update(kline)

    history_deltas = [
        dict(open=history_datas[i].open - history_datas[i - 1].open,
             high=history_datas[i].high - history_datas[i - 1].high,
             low=history_datas[i].low - history_datas[i - 1].low,
             close=history_datas[i].close - history_datas[i - 1].close)
        for i in range(1, len(history_datas))]

    # 取历史数据最后一根K线作为初始基准K线
    base_kline = copy.deepcopy(history_datas[-1])
    base_kline.datetime = start_datetime

    random.seed()

    while True:
        for delta in (history_deltas[random.randint(0, len(history_deltas) - 1)] for _ in range(len(history_deltas))):
            base_kline.open += delta['open']
            base_kline.high += delta['high']
            base_kline.low += delta['low']
            base_kline.close += delta['close']

        db_client[ctakline.KLINE_DB_NAMES[period]][gen_collection].replace_one(
                dict(datetime=base_kline.datetime), base_kline.__dict__, upsert=True)

        base_kline.datetime += dt.timedelta(minutes=ctakline.MINUTES_OF_PERIOD[period])
        if base_kline.datetime > end_datetime:
            break


if __name__ == '__main__':
    generate(ctakline.PERIOD_15MIN,
             '20160525', '20161206', 'RB1701',
             '20180101', '20280101', 'RB1701TEST')
