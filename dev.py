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


def strat(api: provider.BitvavoRestClient, market: str):
    symbol, quote = market.split('-')
    dataset = api.current
    eur = api.get_balance(quote)[0]['available']
    btc = api.get_balance(symbol)[0]['available']
    try:
        history = api.get_trades(market)[0]['price']
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
    wallet_start = 1000
    market = 'ETH-EUR'
    
    value_start = 0
    symbol, quote = market.split('-')

    # prepare data, based on saved data, or refresh and save
    data = load(market, '1h')
    data = []
    if not len(data):
        api = provider.BitvavoRestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])
        data = api.get_data(market=market, interval='1h', number=40)
        save(data, market, '1h')


    # set up test environment
    data = apply_indicators(data)
    api = provider.TestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'], data=data, balance={'EUR': wallet_start})
    

    # step through test data
    step = True
    while step:
        step = api.step()
        data = api.get_data()

        if not value_start:
            value_start = data.iloc[-1].close
        
        eur = float(api.get_balance(symbol='EUR')[0]['available'])
        sym = float(api.get_balance(symbol=symbol)[0]['available'])
        
        buy, sell = strat(api, market)
        if buy:
            result = api.place_order(market=market, side='buy', order_type='market', amountQuote=eur)
        if sell:
            result = api.place_order(market=market, side='sell', order_type='market', amount=sym)
        print(f'{data.iloc[-1].Date:19s}  EUR={eur:016.2f}  {symbol}={sym:016.4f}', end='\r')
    
    print()

    value_end = data.iloc[-1].close
    market_performance = value_end/value_start
    wallet_end = eur+(value_end*sym)
    algo_performance = wallet_end/wallet_start


    print(f'Value start:        {value_start:.2f} EUR')
    print(f'Value end:          {value_end:.2f} EUR')
    print(f'Market performance: {market_performance:.2f}%')
    print()
    print(f'Wallet start:       {wallet_start:.2f} EUR')
    print(f'Wallet end:         {wallet_end:.2f} EUR')
    print(f'Algo performance:   {algo_performance:.2f}%')



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
