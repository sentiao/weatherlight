import sys
import os
import pickle
import re
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


def apply_indicators(dataset):
    
    indicator_list = [
        (indicators.ema, 240, 'ema120c'),
        (indicators.ema, 240, 'ema240c'),
        (indicators.ema, 360, 'ema360c'),
        (indicators.rsi, 10, 'rsi10c'),
        (indicators.rsi, 25, 'rsi25c'),
        (indicators.rsi, 50, 'rsi50c'),
        (indicators.rsi, 100, 'rsi100c'),
        (indicators.sma, 120, 'sma120c'),
        (indicators.sma, 240, 'sma240c'),
        (indicators.sma, 360, 'sma360c'),
        (indicators.ema, 240, 'ema120v', 'volume'),
        (indicators.ema, 240, 'ema240v', 'volume'),
        (indicators.ema, 360, 'ema360v', 'volume'),
        (indicators.rsi, 10, 'rsi10v', 'volume'),
        (indicators.rsi, 25, 'rsi25v', 'volume'),
        (indicators.rsi, 50, 'rsi50v', 'volume'),
        (indicators.rsi, 100, 'rsi100v', 'volume'),
        (indicators.sma, 120, 'sma120v', 'volume'),
        (indicators.sma, 240, 'sma240v', 'volume'),
        (indicators.sma, 360, 'sma360v', 'volume'),
    ]

    for indicator in indicator_list:
        func = indicator[0]
        args = indicator[1:]
        print(f'{func} {args}')
        func(dataset, *args)

    print('dropna')
    dataset.dropna(axis=0, inplace=True)
    print('reset index')
    dataset = dataset.reset_index(drop=True)
    return dataset


def strat(api: provider.BitvavoRestClient, market: str):
    symbol, quote = market.split('-')
    data = api.current
    eur = api.get_balance(quote)[0]['available']
    btc = api.get_balance(symbol)[0]['available']
    try:
        history = api.get_trades(market)[0]['price']
    except:
        history = 0
    
    buy_signal = (data.iloc[-1].rsi25c > 70.0) & (data.iloc[-1].close > data.iloc[-1].ema360c) & (btc == 0) & (eur > 10)
    sell_signal = (btc != 0) & (30 > data.iloc[-1].rsi25c) & (data.iloc[-1].close > history * 1.0025) & (data.iloc[-1].ema240c > data.iloc[-1].close) | (btc != 0) & (history * 0.95 > data.iloc[-1].close)

    if buy_signal and sell_signal:
        buy_signal = False

    return buy_signal, sell_signal

def test():
    market = 'ETH-EUR'
    interval = '1h'
    
    symbol, quote = market.split('-')

    
    
    # prepare data, based on saved data, or refresh and save
    data = load(market, interval)    
    if not len(data):
        api = provider.BitvavoRestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])
        data = api.get_data(market=market, interval=interval, number=2)
        save(data, market, interval)

    # set up test environment
    value_start = 0
    wallet_start = 1000
    print('Apply indicators')
    data = apply_indicators(data)
    api = provider.TestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'], data=data, balance={'EUR': 1000})

    # set up incubator
    incubator = gdl.Incubator(size=8, length=2, api_init=provider.TestClient, api_args={
        'api_key': provider.settings()['key'],
        'api_secret': provider.settings()['secret']
    })

    # step through test data
    step = True
    while step:
        step = api.step()
        data = api.get_data()

        incubator.init(data=data, balance={'EUR':1000})
        incubator.develop()
        print([float(ind['api'].net_worth(symbol)) for ind in incubator.population])
        incubator.reset()


        continue

        if not value_start:
            value_start = data.iloc[-1].close
        
        eur = float(api.get_balance(symbol='EUR')[0]['available'])
        sym = float(api.get_balance(symbol=symbol)[0]['available'])
        
        # todo:
        # strat needs to have state, be grown before the first run, and then iterate With the data
        buy, sell = strat(api, market)
        if buy:
            result = api.place_order(market=market, side='buy', order_type='market', amountQuote=eur)
        if sell:
            result = api.place_order(market=market, side='sell', order_type='market', amount=sym)
        print(f'{data.iloc[-1].Date:19s}  EUR={eur:016.2f}  {symbol}={sym:016.4f}', end='\r')
    
    print()

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


def status():
    api = provider.BitvavoRestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])
    # status
    print('--status--')
    eur = float(api.get_balance('EUR')[0]['available'])
    print(f'{eur=}')
    btc = float(api.get_balance('BTC')[0]['available'])
    print(f'{btc=}')
    trades = api.get_trades(market='BTC-EUR')[0]
    print(f'{trades=}')



if __name__ == '__main__':
    if '--test' in sys.argv: test()
    if '--status' in sys.argv: status()
    if '--dev' in sys.argv:
        import gdl

        
        chromosome = gdl.new_chromosome(length=1)
        function = gdl.to_function(chromosome=chromosome, template='data[{}%5]')

        # data.iloc[0].iloc[4:-1]

        api = provider.BitvavoRestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])
        breakpoint()
