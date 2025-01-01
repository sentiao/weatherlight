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


def apply_indicators(data):
    indicator_list = [
        (indicators.ema, 240, 'ema120c'),
        (indicators.ema, 240, 'ema240c'),
        (indicators.ema, 360, 'ema360c'),
        (indicators.rsi, 25, 'rsi25c'),
    ]

    for indicator in indicator_list:
        func = indicator[0]
        args = indicator[1:]
        func(data, *args)

    data.dropna(axis=0, inplace=True)
    data = data.reset_index(drop=True)
    return data


def strat1(api: provider.BitvavoRestClient, market: str, indicators: bool):
    # indicators: tell strat if it still needs to apply indicators itself, or not
    # since the strat grabs data from api itself and the test environment has preloaded indicators for performance reasons, and live data has not

    symbol, quote = market.split('-')
    data = api.get_data(market, '1h', 1440, 1)
    if not indicators: data = apply_indicators(data)
    eur = api.get_balance(quote)[0]['available']
    sym = api.get_balance(symbol)[0]['available']
    for trade in api.get_trades(market):
        if trade.get('side', '') != 'buy': continue
        history = trade.get('price', 0.0)
        break
    else:
        history = 0.0
    
    buy_signal = \
        (sym == 0) & (eur > 10) & \
        (data.iloc[-1].rsi25c > 70.0) & \
        (data.iloc[-1].close > data.iloc[-1].ema360c)
    
    sell_signal = \
        (sym != 0) & \
        (30 > data.iloc[-1].rsi25c) & \
        (data.iloc[-1].close > history * 1.0025) & \
        (data.iloc[-1].ema240c > data.iloc[-1].close) | \
        (sym != 0) & (history * 0.95 > data.iloc[-1].close) # stoploss

    if buy_signal and sell_signal:
        buy_signal = False

    return buy_signal, sell_signal


def test():
    LOG = False

    market = 'ETH-EUR'
    interval = '1h'
    symbol, quote = market.split('-')
    if LOG:
        with open('c:/temp/out.csv', 'w') as fh:
            fh.write('date,price,worth\n')
    # prepare data, based on saved data, or refresh and save
    data = load(market, interval)
    if not len(data):
        api = provider.BitvavoRestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])
        data = api.get_data(market=market, interval=interval, number=100)
        save(data, market, interval)

    # set up test environment
    value_start = 0
    wallet_start = 1000
    data = apply_indicators(data)
    api = provider.TestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'], balance={'EUR': wallet_start})
    api.set_data(data)

    # step through test data
    step = True
    while step:
        step = api.step()
        data = api.get_data()


        # metrics
        if not value_start:
            value_start = data.iloc[-1].close
        
        eur = float(api.get_balance(symbol='EUR')[0]['available'])
        sym = float(api.get_balance(symbol=symbol)[0]['available'])
        
        # strat
        buy, sell = strat1(api, market, True)

        if buy:
            result = api.place_order(market=market, side='buy', order_type='market', amountQuote=eur)
        if sell:
            result = api.place_order(market=market, side='sell', order_type='market', amount=sym)
        if buy or sell:
            print(f'{data.iloc[-1].Date:19s}  EUR={eur:016.2f}  {symbol}={sym:016.4f}  WORTH={api.net_worth(symbol):16.4f}')
            
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
        api = provider.BitvavoRestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])
        breakpoint()
