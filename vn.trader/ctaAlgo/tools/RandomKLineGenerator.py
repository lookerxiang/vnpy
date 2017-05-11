# encoding: UTF-8

import copy
import datetime as dt
import math
import random

import pymongo

import dataRecorder.drEngineEx.ctaKLine as ctakline


def generate(period,
             history_start_date, history_end_date, history_collection,
             gen_start_date, gen_end_date, gen_collection,
             max_continuous=10):
    """随机生成K线数据
    
    :param period:              K线周期，指定 dataRecorder.drEngineEx.ctaKLine 中定义的值
    :param history_start_date:  历史K线数据开始日期 'YYYYMMDD'
    :param history_end_date:    历史K线数据结束日期 'YYYYMMDD'
    :param history_collection:  历史K线数据文档名
    :param gen_start_date:      生成K线起始日期 'YYYYMMDD'
    :param gen_end_date:        生成K线结束日期 'YYYYMMDD'
    :param gen_collection:      生成K线数据文档名
    :param max_continuous:      最大连续历史涨跌再现数目      
    :return: 
    """
    # 计算历史K线数据和生成K线数据的起始和结束时间
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

    # 从数据库中抽取历史数据
    history_datas = []
    for kline in db_client[ctakline.KLINE_DB_NAMES[period]][history_collection].find(
            filter={'datetime': {'$gte': history_start_datetime,
                                 '$lte': history_end_datetime}},
            projection={'_id': False},
            sort=(('datetime', pymongo.ASCENDING),)):
        history_datas.append(ctakline.KLine(None))
        history_datas[-1].__dict__.update(kline)

    # 计算历史数据中K线high/low与open/close差值的均值和标准差，用于使用正态分布随机数
    mean_high_diff = sum(map(lambda k: k.high - max(k.open, k.close), history_datas)) // len(history_datas)
    mean_low_diff = sum(map(lambda k: min(k.open, k.close) - k.low, history_datas)) // len(history_datas)
    standard_deviation_high_diff = math.sqrt(
            sum(map(lambda k: (k.high - max(k.open, k.close) - mean_high_diff) ** 2, history_datas)) //
            len(history_datas))
    standard_deviation_low_diff = math.sqrt(
            sum(map(lambda k: (min(k.open, k.close) - k.low - mean_low_diff) ** 2, history_datas)) //
            len(history_datas))

    # 计算历史K线中high/low与open/close差值的最大值和最小值
    hl_limit_max = max(map(lambda k: max(k.high - max(k.open, k.low), min(k.open, k.close) - k.low), history_datas))
    hl_limit_min = min(map(lambda k: min(k.high - max(k.open, k.low), min(k.open, k.close) - k.low), history_datas))

    # 计算历史数据中前后K线的差值数据
    history_deltas = [dict(diff=(history_datas[i].close - history_datas[i - 1].open) // 2,
                           jump=history_datas[i].open - history_datas[i - 1].close, )
                      for i in range(1, len(history_datas))]
    history_deltas.extend([dict(diff=-delta['diff'], jump=-delta['jump'], )
                           for delta in history_deltas])

    # 取历史数据最后一根K线作为初始基准K线
    base_kline = copy.deepcopy(history_datas[-1])
    base_kline.datetime = start_datetime

    # 以第一根K线的close值作为震荡偏移的基准值，计算涨跌概率用
    base_close = base_kline.close
    # 初始涨跌概率
    updown_probability = 0.5

    # 初始化种子
    random.seed()

    # 清除数据库并确保索引建立（超大量数据未建立索引排序将导致失败）
    db_client[ctakline.KLINE_DB_NAMES[period]][gen_collection].delete_many({})
    db_client[ctakline.KLINE_DB_NAMES[period]][gen_collection].create_index('datetime')

    # 数据库插入缓存
    insert_cache = []

    # 差值数据下标，一次会连续取最多max_continuousgege个
    delta_indexes = []

    while True:
        # 上一次取到的差值数据下标已用完
        if len(delta_indexes) == 0:
            # 判断是涨还是跌
            is_up = random.random() < updown_probability

            # 取满足涨跌要求的差值数据下标起点
            while True:
                rand_index = random.randint(0, len(history_deltas) - 1)
                if is_up:
                    if history_deltas[rand_index]['diff'] >= 0:
                        break
                else:
                    if history_deltas[rand_index]['diff'] <= 0:
                        break

            # 将下标起点开始最多max_continuousgege个下标存放到列表中
            delta_indexes.extend(range(rand_index,
                                       min(rand_index + random.randint(1, max_continuous), len(history_deltas))))
            # 使用pop从后面依次取，因此逆序
            delta_indexes.reverse()

        # 获取对应的差值数据
        random_delta = history_deltas[delta_indexes.pop()]

        # 根据上一轮K线的close值计算新K线的open/close值
        base_kline.open = base_kline.close + random_delta['jump']
        base_kline.close = base_kline.open + random_delta['diff']

        # 由正态分布取high/low相对open/close的偏移量，计算出新的high/low值
        base_kline.high = round(
                min(hl_limit_max,
                    max(hl_limit_min,
                        random.normalvariate(mean_high_diff, standard_deviation_high_diff))) +
                max(base_kline.open, base_kline.close))
        base_kline.low = round(
                min(base_kline.open, base_kline.close) -
                min(hl_limit_max,
                    max(hl_limit_min,
                        random.normalvariate(mean_low_diff, standard_deviation_low_diff))))

        assert (base_kline.low <= base_kline.open <= base_kline.high)
        assert (base_kline.low <= base_kline.close <= base_kline.high)

        # 插入缓存每满10000条时执行mongodb插入
        insert_cache.append(copy.deepcopy(base_kline.__dict__))
        if len(insert_cache) >= 10000:
            db_client[ctakline.KLINE_DB_NAMES[period]][gen_collection].insert_many(insert_cache)
            insert_cache = []

        # 更新下一条K线的时间
        base_kline.datetime += dt.timedelta(minutes=ctakline.MINUTES_OF_PERIOD[period])
        if base_kline.datetime > end_datetime:
            break

        # 重新计算涨跌概率
        updown_probability = max(0, min(1, 0.5 - (base_kline.close - base_close) * 0.0001))

    # 绘图
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt

    plt.figure(1)
    klines = list(db_client[ctakline.KLINE_DB_NAMES[period]][gen_collection].find(
            sort=(('datetime', pymongo.ASCENDING),)))
    plt.plot(map(lambda k: k['datetime'], klines),
             map(lambda k: k['close'], klines))
    plt.show()


if __name__ == '__main__':
    generate(ctakline.PERIOD_30MIN,
             '20151127', '20170504', 'RB0000',
             '20180101', '20280101', 'RB0000TEST')
