import matplotlib.pyplot as plt
import numpy
import talib as ta
from influxdb import *
from mpl_finance import candlestick2_ohlc

import eval
import filter


def get_data(begin, end, exchange, duration, market_symbol):
    # InfluxDB configuration
    db_host = 'localhost'
    db_port = 8086
    db_user = 'CryptoMarketDataCollector'
    db_pw = '01101011'
    db_name = 'CryptoMarketData'
    engine = InfluxDBClient(host=db_host, port=db_port, username=db_user, password=db_pw, database=db_name)
    engine.switch_database(db_name)
    engine.switch_user(db_user, db_pw)

    # Configure input data
    base = market_symbol.split('/')[0]
    quote = market_symbol.split('/')[1]

    # Getting the data
    q = engine.query('SELECT * FROM {} WHERE time >= {} AND time <= {}'.format(exchange, begin, end))
    data = q.get_points(tags={'duration': duration,
                              'market': market_symbol})
    return data


def format_data(data):
    # Formatting data
    closes = []
    opens = []
    highs = []
    lows = []
    for line in data:
        closes.append(line['close'])
        opens.append(line['open'])
        highs.append(line['high'])
        lows.append(line['low'])

    o = numpy.array(opens, dtype=float)
    h = numpy.array(highs, dtype=float)
    l = numpy.array(lows, dtype=float)
    c = numpy.array(closes, dtype=float)
    return o, h, l, c


def plot_price_and_eval(o, h, l, c, eval):
    # Plotting data and result
    fig, axes = plt.subplots(nrows=1, ncols=1)
    candlestick2_ohlc(axes, o, h, l, c, colorup='black', colordown='b', width=0.3)
    for i in range(0, len(eval)):
        if eval[i] > 0:
            plt.axvline(i, c='green')
        elif eval[i] < 0:
            plt.axvline(i, c='red')

    plt.show()


def plot_capital(percent_of_capital, eval):
    # Plotting data and result
    init_cap = 1000
    cap = [init_cap]
    for i in eval:
        if i > 0:
            cap.append(cap[-1] + cap[-1]*(percent_of_capital/100))
        elif i < 0:
            cap.append(cap[-1] - cap[-1]*(percent_of_capital/100))

    plt.xlabel("# trades")
    plt.ylabel("Capital")
    plt.plot(cap, color='dodgerblue')
    plt.axhline(init_cap, c='black')
    plt.show()
    return 100. * (cap[-1] / init_cap)


def compute_max_drawdown(tab):
    new_tab = []
    for i in tab:
        if i != 0:
            new_tab.append(i)

    all_time_max = 0
    count = 1
    for i in range(1, len(new_tab)):
        if new_tab[i-1] == -1 and new_tab[i] == -1:
            count += 1
        else:
            all_time_max = max(count, all_time_max)
            count = 1
    all_time_max = max(count, all_time_max)
    return all_time_max


def search_lower(prices):
    low = 1000000000000
    for p in prices:
        if p < low:
            low = p
    return low


def search_higher(prices):
    high = 0
    for p in prices:
        if p > high:
            high = p
    return high


def main():
    begin = "'2018-03-01T00:00:00Z'"
    end = "'2018-10-01T10:00:00Z'"
    exchange = 'poloniex'
    duration = '4h'
    market_symbol = 'BTC/USDT'
    data = get_data(begin, end, exchange, duration, market_symbol)
    o, h, l, c = format_data(data)

    # tab_cor = ta.CDLDOJI(o, h, l, c)
    # tab_cor = ta.CDLDOJISTAR(o, h, l, c)
    # tab_cor = ta.CDLSHOOTINGSTAR(o, h, l, c)
    tab_cor = ta.CDLBELTHOLD(o, h, l, c)
    # tab_cor = ta.CDLCOUNTERATTACK(o, h, l, c)
    # tab_cor = ta.CDLHAMMER(o, h, l, c)
    # tab_cor = randompattern.random(len(o))

    print(str(tab_cor))
    tab_cor = filter.ema_filter(c, tab_cor, direction='bullish', ma=9)
    # tab_cor = amplitude_filter(h, l, tab_cor, min_amplitude=0.01)
    print(str(tab_cor))

    koef = 1
    percent_of_capital = 5
    candle_timeframe = 25
    evaluation = eval.continuation_higher_than_risk_n_timeframe_with_stoploss(o, h, l, c, tab_cor, k=koef,
                                                                              n=candle_timeframe, plot=True)
    # Plot graphs
    plot_price_and_eval(o, h, l, c, evaluation)
    final_cap = plot_capital(percent_of_capital, evaluation)

    win = 0
    loss = 0
    for i in evaluation:
        if i > 0:
            win += 1
        elif i < 0:
            loss += 1

    # Let's print all the stuff
    print("\n\n##################################################################")
    print("Benchmark between {} {} and {} {}".format(begin[1:11], begin[12:-2], end[1:11], end[12:-2]))
    print("Benchmark on {} {} chart from {}".format(market_symbol, duration, exchange))
    print("Start Price        : {}".format(o[0]))
    higher = search_higher(h)
    print("Higher Price       : {}".format(higher))
    lower = search_lower(l)
    print("Lower Price        : {}".format(lower))
    print("End Price          : {}".format(c[-1]))
    print("Win Trade          : {}".format(win))
    print("Loss Trade         : {}".format(loss))
    total = win + loss
    print("Total Trade        : {}".format(total))
    win_rate = 100 * (win / total)
    print("Win Rate           : {:.5} %".format(win_rate))
    loss_rate = 100 * (loss / total)
    print("Loss Rate          : {:.5} %".format(loss_rate))
    print("TP/SL coef (k)     : {}".format(koef))
    exp = win * koef - 1 * loss
    print("Expectancy (R)     : {} R (for {}R risked)".format(exp, total))
    exp_moy = exp / total
    print("Expectancy (R moy) : {:.5}".format(exp_moy))
    gain = (100 * (1 + (exp_moy*percent_of_capital / 100)) ** total)
    print("With R={}%          : {:.5} % expected capital".format(percent_of_capital, gain))
    print("With R={}%          : {:.5} % real final capital".format(percent_of_capital, final_cap))
    max_lost_streak = compute_max_drawdown(evaluation)
    print("Max lost streak    : {}".format(max_lost_streak))
    max_lost_streak_in_percent = 100 - (100 * (1 - (percent_of_capital/100)) ** max_lost_streak)
    print("Max drawdown       : {:.5} %".format(max_lost_streak_in_percent))
    print("##################################################################")


if __name__ == '__main__':
    main()
