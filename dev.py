import sys
import os
import pickle
import numpy as np
import pandas as pd
import indicators
import provider


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
        (indicators.ema, 240, 'ema240c'),
        (indicators.ema, 360, 'ema360c'),
        (indicators.rsi, 25, 'rsi25c'),
        (indicators.atr, 50, 'atr50c'),
    ]

    for indicator in indicator_list:
        func = indicator[0]
        args = indicator[1:]
        func(dataset, *args)

    dataset.dropna(axis=0, inplace=True)
    dataset = dataset.reset_index(drop=True)
    return dataset


def strat(api: provider.BitvavoRestClient):
    dataset = provider.to_dataset(api.current)
    dataset = apply_indicators(dataset)
    eur = api.get_balance('EUR')[0]['available']
    btc = api.get_balance('BTC')[0]['available']
    try:
        history = api.get_trades('BTC-EUR')[0]['price']
    except:
        history = 0

    buy_signal = all([
        btc == 0,
        eur > 10,
        dataset.iloc[-1].rsi25c > 70,
        dataset.iloc[-1].close > dataset.iloc[-1].ema360c,
    ])


    sell_signal = any([all([
        btc != 0,
        30 > dataset.iloc[-1].rsi25c,
        dataset.iloc[-1].close > history * 1.0025,
        dataset.iloc[-1].ema240c > dataset.iloc[-1].close,
    ]), all([
        btc != 0,
        history * 0.95 > dataset.iloc[-1].close
    ])])

    if buy_signal and sell_signal:
        buy_signal = False


    return buy_signal, sell_signal


def backtest():
    
    market = 'ETH-EUR'
    symbol = 'ETH'

    # prepare data, based on saved data, or refresh and save
    data = load(market, '1h')
    if not len(data):
        api = provider.BitvavoRestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])
        data = api.get_data(market=market, interval='1h', number=40)
        save(data, market, '1h')
    
    # set up test environment
    api = provider.TestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'], data=data, balance={'EUR': 1000})
    
    # step through test data
    step = True
    while step:
        step = api.step()
        
        data = api.get_data()
        dataset = provider.to_dataset(data)
        
        eur = float(api.get_balance(symbol='EUR')[0]['available'])
        btc = float(api.get_balance(symbol=symbol)[0]['available'])
        
        buy, sell = strat(api)
        if buy:
            result = api.place_order(market=market, side='buy', order_type='market', amountQuote=eur)
            print('BOUGHT', end='\r')
        if sell:
            result = api.place_order(market=market, side='sell', order_type='market', amount=btc)
            print('SOLD', end='\r')
        print(f'       {dataset.iloc[-1].date:19s}  EUR={eur:016.2f}  {symbol}={btc:016.4f}', end='\r')
    
    print()



def test():
    api = provider.BitvavoRestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])

    # status
    print('--status--')
    eur = float(api.get_balance(symbol='EUR')[0]['available'])
    print(f'{eur=}')
    btc = float(api.get_balance(symbol='BTC')[0]['available'])
    print(f'{btc=}')

    print('--buy--')
    result = api.place_order(market='BTC-EUR', side='buy', order_type='market', amountQuote=eur)
    print(result)
    print('--sell--')
    result = api.place_order(market='BTC-EUR', side='sell', order_type='market', amount=btc)
    print(result)

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
    if '--backtest' in sys.argv: backtest()
    if '--status' in sys.argv: status()
    if '--dev' in sys.argv:
        api = provider.BitvavoRestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])
        print(api.get_trades('BTC-EUR')[0])
        breakpoint()
