import sys
import os
import pickle
import re
import json
from copy import deepcopy
from time import sleep
import numpy as np
import indicators
import provider
import algo


settings = {'key':'', 'secret':''}
for arg in sys.argv:
    if not '.json' in arg: continue
    with open(arg, 'r') as fh:
        settings = json.load(fh)


def load(market, interval):
    data_fn = f'data/data-{market}-{interval}.dat'
    data = []
    if os.path.exists(data_fn):
        with open(data_fn, 'rb') as fh:
            data = pickle.load(fh)
    return data


def save(data, market, interval):
    with open(f'data/data-{market}-{interval}.dat', 'wb') as fh:
        pickle.dump(data, fh)


def apply_gdl_indicators(data):
    for indicator in [indicators.ema, indicators.sma, indicators.rsi]:
        for period in [3, 5, 8, 13, 21, 34, 55, 89, 144]:
            data = indicator(data, period, 4)
            data = indicator(data, period, 5)
    
    while np.isnan(data[0]).any():
        data = np.delete(data, 0, axis=0)

    return data


def apply_indicators(data):    
    # timestamp     open    high    low     close   volume
    # 0             1       2       3       4       5
    indicator_list = [
        (indicators.ema, 240),
        (indicators.ema, 360),
        (indicators.rsi, 24),
    ]

    for indicator in indicator_list:
        func = indicator[0]
        args = indicator[1:]
        data = func(data, *args)
    
    while np.isnan(data[0]).any():
        data = np.delete(data, 0, axis=0)

    return data


def strategy(api: provider.RestClient, market: str, interval: str, indicators: bool): # tuned for 1h
    # indicators: tell strat if it still needs to apply indicators itself, or not
    # since the strat grabs data from api itself and the test environment has preloaded indicators for performance reasons, and live data has not

    symbol, quote = market.split('-')
    data = api.get_data(market, interval, 1440, 1)
    if not indicators: data = apply_indicators(data)
    try: quo = float(api.get_balance(quote)[0]['available'])
    except: quo = 0.0
    try: sym = float(api.get_balance(symbol)[0]['available'])
    except: sym = 0.0

    for trade in api.get_trades(market):
        if trade.get('side', '') != 'buy': continue
        history = float(trade.get('price', 0.0))
        break
    else:
        history = 0.0

    buy_signal = \
        (sym == 0) & (quo > 10) & \
        (data[-1, 8] > 70.0) & \
        (data[-1, 4] > data[-1, 7])
    
    sell_signal = \
        (sym != 0) & \
        (30 > data[-1, 8]) & \
        (data[-1, 4] > history * 1.0025) & \
        (data[-1, 6] > data[-1, 4]) | \
        (sym != 0) & (history * 0.95 > data[-1, 4]) # stoploss

    if buy_signal and sell_signal:
        buy_signal, sell_signal = False, False
    
    return buy_signal, sell_signal



def incubator():

    # parameters
    market = 'ETH-EUR'
    interval = '1d'
    value_start = 0
    wallet_start = 1000

    # prepare data, based on saved data, or refresh and save
    symbol, quote = market.split('-')
    data = load(market, interval)
    if not len(data):
        api = provider.RestClient(api_key=settings['key'], api_secret=settings['secret'])
        data = api.get_data(market=market, interval=interval, number=-1)
        save(data, market, interval)
    
    # set up test environment
    api = provider.TestClient()
    api.set_balance(balance={'EUR': wallet_start})
    api.set_data(data=data)
    
    # set up incubator
    population_size = 32
    gene_size = 8
    mutation_rate = 0.02
    
    incubation_period = 5
    reincubation_period = 5
    window_size = 1440

    incubator = algo.Incubator(api_class=provider.TestClient, market=market, interval=interval, window_size=window_size, population_size=population_size, gene_size=gene_size, mutation_rate=mutation_rate)
    actor = None

    # step through test data
    counter, alive = -1, True
    while alive:
        counter, alive = api.step(counter, window_size)
        data = api.get_data()
        data = apply_gdl_indicators(data)

        # template
        row_length = len(data[-1]) - 1
        template = f'data[-1, (__number__ % {row_length})+1]'

        # metrics
        if not value_start:
            value_start = data[-1, 4]
        
        # strat
        while incubation_period:
            incubation_period -= 1
            buy, sell, stoploss = incubator.run(data, template)
        incubation_period = reincubation_period # for next run

        print(f'--> {provider.to_date(data[-1, 0])}')
        
        # get most recent interacted price
        for trade in api.get_trades(market):
            if trade.get('side', '') != 'buy': continue
            history = trade.get('price', 0.0)
            break
        else:
            history = 0.0

        # act
        quo = float(api.get_balance(symbol=quote)[0]['available'])
        sym = float(api.get_balance(symbol=symbol)[0]['available'])

        buy_signal = eval(buy) & (sym == 0) & (quo > 10)
        sell_signal = (sym != 0) & (history * stoploss > data[-1, 4]) | (sym != 0) & eval(sell)

        if buy_signal and sell_signal:
            buy_signal, sell_signal = False, False
        
        if buy_signal:
            result = api.place_order(market=market, side='buy', order_type='market', amountQuote=quo)
            print('BUY  ', end='')
        if sell_signal:
            result = api.place_order(market=market, side='sell', order_type='market', amount=sym)
            print('SELL ', end='')
        
        if buy_signal or sell_signal:
            print(f'{provider.to_date(data[-1, 0]):19s}  EUR={quo:016.2f}  {symbol}={sym:016.4f}  WORTH={api.net_worth(symbol):16.4f}')

    # metrics
    value_end = data[-1, 4]
    market_performance = ((value_end/value_start)-1)*100
    wallet_end = api.net_worth(symbol)
    algo_performance = ((wallet_end/wallet_start)-1)*100

    print(f'Value start:        {value_start:.2f} EUR')
    print(f'Value end:          {value_end:.2f} EUR')
    print(f'Market performance: {market_performance:.2f}%')
    print()
    print(f'Wallet start:       {wallet_start:.2f} EUR')
    print(f'Wallet end:         {wallet_end:.2f} EUR')
    print(f'Algo performance:   {algo_performance:.2f}%')





def test():
    with open('logs/out.csv', 'w') as fh:
        fh.write('date,price,worth\n')

    # parameters
    market = 'ETH-EUR'
    interval = '1h'
    value_start = 0
    wallet_start = 1000
    spent = wallet_start

    # prepare data, based on saved data, or refresh and save
    symbol, quote = market.split('-')
    data = load(market, interval)
    if not len(data):
        api = provider.RestClient(api_key=settings['key'], api_secret=settings['secret'])
        data = api.get_data(market=market, interval=interval, number=-1)
        save(data, market, interval)
    data = apply_indicators(data)


    # set up test environment
    api = provider.TestClient()
    api.set_data(data)
    api.set_balance(balance={'EUR': wallet_start})
    
    h_month = 0

    # step through test data
    step_counter, step = -1, True
    while step:
        step_counter, step = api.step(step_counter, 1)
        data = api.get_data()

        # metrics
        if not value_start:
            value_start = data[-1, 4]
        
        # strategy
        buy, sell = strategy(api, market, interval, True)

        # act
        quo = float(api.get_balance(symbol=quote)[0]['available'])
        sym = float(api.get_balance(symbol=symbol)[0]['available'])
        if buy:
            result = api.place_order(market=market, side='buy', order_type='market', amountQuote=quo)
        if sell:
            result = api.place_order(market=market, side='sell', order_type='market', amount=sym)
        
        if buy or sell:
            if buy: print('BUY ', end=' ')
            if sell: print('SELL', end=' ')
            print(f'{provider.to_date(data[-1][0]):19s} {quo:16.2f} EUR  {sym:16.4f} {symbol}  {api.net_worth(symbol):16.4f} EUR worth')

            with open('logs/out.csv', 'a') as fh:
                fh.write(f'{provider.to_date(data[-1, 0])},{data[-1][4]},{api.net_worth(symbol)}\n')

    # metrics
    value_end = data[-1, 4]
    market_performance = ((value_end/value_start)-1)*100
    wallet_end = api.net_worth(symbol) - spent
    algo_performance = ((wallet_end/wallet_start)-1)*100

    print(f'Value start:        {value_start:.2f} EUR')
    print(f'Value end:          {value_end:.2f} EUR')
    print(f'Market performance: {market_performance:.2f}%')
    print()
    print(f'Wallet start:       {wallet_start:.2f} EUR')
    print(f'Spent:              {spent:.2f} EUR')
    print(f'Wallet end:         {wallet_end:.2f} EUR')
    print(f'Algo performance:   {algo_performance:.2f}%')


def status(market : str = 'ETH-EUR'):
    symbol, quote = market.split('-')
    api = provider.RestClient(api_key=settings['key'], api_secret=settings['secret'])
    # status
    print('--status--')
    quo = float(api.get_balance(quote)[0]['available'])
    print(f'{quo=}')
    btc = float(api.get_balance(symbol)[0]['available'])
    print(f'{btc=}')
    trades = api.get_trades(market=market)[0]
    print(f'{trades=}')



def live():
    # parameters
    market = 'ETH-EUR'
    interval = '1h'

    symbol, quote = market.split('-')
    semaphore = None
    api = provider.RestClient(api_key=settings['key'], api_secret=settings['secret'])

    while True:

        # get data
        data = api.get_data(market=market, interval=interval, number=1)

        # semaphore
        if data[-1, 0] == semaphore:
            sleep(20)
            continue
        else:
            semaphore = data[-1, 0]

        # report
        print(provider.to_date(semaphore))

        # strategy
        buy, sell = strategy(api, market, interval, False)

        # act
        try: quo = float(api.get_balance(symbol=quote)[0]['available'])
        except: quo = 0.0
        try: sym = float(api.get_balance(symbol=symbol)[0]['available'])
        except: quo = 0.0
        
        if buy:
            result = api.place_order(market=market, side='buy', order_type='market', amountQuote=quo)
        if sell:
            result = api.place_order(market=market, side='sell', order_type='market', amount=sym)

        # report
        if buy or sell:
            if buy: print('BUY ', end=' ')
            if sell: print('SELL', end=' ')
            print(f'{provider.to_date(data[-1, 0]):19s} {quo:16.2f} EUR  {sym:16.4f} {symbol}')


if __name__ == '__main__':
    if '--incubator' in sys.argv: incubator()
    if '--test' in sys.argv: test()
    if '--gdl' in sys.argv: test_gdl()
    if '--status' in sys.argv: status()
    if '--dev' in sys.argv:
        api = provider.RestClient(api_key=settings['key'], api_secret=settings['secret'])
        market = 'ETH-EUR'
        interval = '1h'
        data1 = api.get_data(market=market, interval=interval, number=1)
        data2 = api.get_data(market=market, interval=interval, number=2)
        data3 = api.get_data(market=market, interval=interval, number=3)
        breakpoint()
    if '--live' in sys.argv: live()