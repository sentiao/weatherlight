import sys
import os
import pickle
import re
from copy import deepcopy
import numpy as np
import pandas as pd
import indicators
import provider
import gdl


def load(market, interval):
    data_fn = f'../data/data-{market}-{interval}.dat'
    data = np.array([])
    if os.path.exists(data_fn):
        with open(data_fn, 'rb') as fh:
            data = pickle.load(fh)
    return data


def save(data, market, interval):
    with open(f'../data/data-{market}-{interval}.dat', 'wb') as fh:
        pickle.dump(data, fh)


def to_date(timestamp):
    return datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')


def apply_indicators(source):
    data = deepcopy(source)
    indicator_list = [
        # old strat
        (indicators.ema, 240, 'ema240c'),
        (indicators.ema, 360, 'ema360c'),
        (indicators.rsi, 25, 'rsi25c'),

        (indicators.sma, 1),

        # for gdl
        (indicators.ema, 12, 'ema12c'),
        (indicators.ema, 24, 'ema24c'),
        (indicators.ema, 36, 'ema36c'),
        (indicators.rsi, 10, 'rsi10c'),
        (indicators.atr, 12, 'atr12c'),
        (indicators.atr, 24, 'atr24c'),
        (indicators.atr, 36, 'atr36c'),

        (indicators.ema, 12, 'ema12v', 'volume'),
        (indicators.ema, 24, 'ema24v', 'volume'),
        (indicators.ema, 36, 'ema36v', 'volume'),
        (indicators.ema, 120, 'ema120v', 'volume'),
        (indicators.ema, 240, 'ema240v', 'volume'),
        (indicators.ema, 360, 'ema360v', 'volume'),
    ]

    for indicator in indicator_list:
        func = indicator[0]
        args = indicator[1:]
        func(data, *args)

    data.dropna(axis=0, inplace=True)
    data = data.reset_index(drop=True)
    return data


def strat(api: provider.RestClient, market: str, indicators: bool):
    # indicators: tell strat if it still needs to apply indicators itself, or not
    # since the strat grabs data from api itself and the test environment has preloaded indicators for performance reasons, and live data has not

    symbol, quote = market.split('-')
    data = api.get_data(market, '1h', 1440, 1)
    if not indicators: data = apply_indicators(data)
    quo = api.get_balance(quote)[0]['available']
    sym = api.get_balance(symbol)[0]['available']
    for trade in api.get_trades(market):
        if trade.get('side', '') != 'buy': continue
        history = trade.get('price', 0.0)
        break
    else:
        history = 0.0
    
    buy_signal = \
        (sym == 0) & (quo > 10) & \
        (data.iloc[-1].rsi25c > 70.0) & \
        (data.iloc[-1].close > data.iloc[-1].ema360c)
    
    sell_signal = \
        (sym != 0) & \
        (30 > data.iloc[-1].rsi25c) & \
        (data.iloc[-1].close > history * 1.0025) & \
        (data.iloc[-1].ema240c > data.iloc[-1].close) | \
        (sym != 0) & (history * 0.95 > data.iloc[-1].close) # stoploss

    if buy_signal and sell_signal: sell_signal = False

    return buy_signal, sell_signal



def test_gdl():

    # parameters
    market = 'ETH-EUR'
    interval = '1h'
    value_start = 0
    wallet_start = 1000

    # prepare data, based on saved data, or refresh and save
    symbol, quote = market.split('-')
    data = load(market, interval)
    if not len(data):
        api = provider.RestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])
        data = api.get_data(market=market, interval=interval, number=100)
        save(data, market, interval)

    # set up test environment
    api = provider.TestClient()
    api.set_data(data)
    api.set_balance(balance={'EUR': wallet_start})
    
    # set up incubator
    incubator = gdl.Incubator(api_class=provider.MultiTestClient, market=market, population_size=128, gene_size=6, mutation_rate=0.1)
    incubation_period = 5

    # step through test data
    step_counter, step = -1, True
    while step:
        step_counter, step = api.step(step_counter, 400)
        data = api.get_data()
        data = apply_indicators(data)
        incubator.set_data(data=data)

        print(f'from {data.iloc[0].Date:19s} to {data.iloc[-1].Date:19s}')

        # metrics
        if not value_start:
            value_start = data.iloc[-1].close
        
        # strat
        buy, sell = False, False
        while incubation_period:
            incubation_period -= 1
            buy, sell = incubator.run()
        incubation_period = 1 # for next run

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
        sell_signal = (sym != 0) & (history * 0.95 > data.iloc[-1].close) | (sym != 0) & eval(sell)

        if buy_signal and sell_signal: sell_signal = False
        
        if buy_signal:
            result = api.place_order(market=market, side='buy', order_type='market', amountQuote=quo)
            print('BUY  ', end='')
        if sell_signal:
            result = api.place_order(market=market, side='sell', order_type='market', amount=sym)
            print('SELL ', end='')
        
        if buy_signal or sell_signal:
            print(f'{data.iloc[-1].Date:19s}  EUR={quo:016.2f}  {symbol}={sym:016.4f}  WORTH={api.net_worth(symbol):16.4f}')

    # metrics
    value_end = data.iloc[-1].close
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
    LOG = False
    if LOG:
        with open('c:/temp/out.csv', 'w') as fh:
            fh.write('date,price,worth\n')

    # parameters
    market = 'ETH-EUR'
    interval = '1h'
    value_start = 0
    wallet_start = 1000


    # prepare data, based on saved data, or refresh and save
    symbol, quote = market.split('-')
    data = load(market, interval)
    if not len(data):
        api = provider.RestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])
        data = api.get_data(market=market, interval=interval, number=100)
        save(data, market, interval)
    data = apply_indicators(data)


    # set up test environment
    api = provider.TestClient()
    api.set_data(data)
    api.set_balance(balance={'EUR': wallet_start})
    # step through test data
    step_counter, step = -1, True
    while step:
        step_counter, step = api.step(step_counter, 1)
        data = api.get_data()

        # metrics
        if not value_start:
            value_start = data.iloc[-1].close
        
        # strat
        buy, sell = strat(api, market, True)

        # act
        quo = float(api.get_balance(symbol=quote)[0]['available'])
        sym = float(api.get_balance(symbol=symbol)[0]['available'])
        if buy:
            result = api.place_order(market=market, side='buy', order_type='market', amountQuote=quo)
        if sell:
            result = api.place_order(market=market, side='sell', order_type='market', amount=sym)
        if buy or sell:
            print(f'{data.iloc[-1].Date:19s}  EUR={quo:016.2f}  {symbol}={sym:016.4f}  WORTH={api.net_worth(symbol):16.4f}')
            
            if LOG:
                with open('c:/temp/out.csv', 'a') as fh:
                    fh.write(f'{data.iloc[-1].Date},{data.iloc[-1].close},{api.net_worth(symbol)}\n')

    # metrics
    value_end = data.iloc[-1].close
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


def status(market : str = 'ETH-EUR'):
    symbol, quote = market.split('-')
    api = provider.RestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])
    # status
    print('--status--')
    quo = float(api.get_balance(quote)[0]['available'])
    print(f'{quo=}')
    btc = float(api.get_balance(symbol)[0]['available'])
    print(f'{btc=}')
    trades = api.get_trades(market=market)[0]
    print(f'{trades=}')



if __name__ == '__main__':
    if '--test' in sys.argv: test()
    if '--test_gdl' in sys.argv: test_gdl()
    if '--status' in sys.argv: status()
    if '--dev' in sys.argv:
        api = provider.RestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])
        data = api.get_data('ETH-EUR', '1h')
        testapi = provider.TestClient()
        testapi.set_data(data)
        testapi.step(0, 1)
        multitestapi = provider.MultiTestClient()
        breakpoint()
    
    if '--gdl' in sys.argv:
        gene = gdl.new_gene(8)
        function = gdl.to_function(gene, f'data.iloc[5:-1][__number__%{4*5}]')
        print(function)
        
        gene = gdl.mutate(gene, 0.02)
        function = gdl.to_function(gene, f'data.iloc[5:-1][__number__%{4*5}]')
        print(function)
        
        breakpoint()
