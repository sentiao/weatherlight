import sys
import os
from datetime import datetime
import pickle
import indicators
import provider



def to_dataset(data):
    data = pd.DataFrame(data, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
    data['timestamp'] = data['date']
    data['date'] = data['date'].apply(lambda n: datetime.fromtimestamp(n/1000).strftime('%Y-%m-%d %H:%M:%S'))
    return data


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
        (indicators.sma, 10, 'sma10c'),
        (indicators.sma, 20, 'sma20c'),
        (indicators.sma, 30, 'sma30c'),
        (indicators.sma, 40, 'sma40c'),
        (indicators.sma, 50, 'sma50c'),
        (indicators.sma, 100, 'sma100c'),
        (indicators.sma, 10, 'sma10v', 'volume'),
        (indicators.sma, 20, 'sma20v', 'volume'),
        (indicators.sma, 30, 'sma30v', 'volume'),
        (indicators.sma, 40, 'sma40v', 'volume'),
        (indicators.sma, 50, 'sma50v', 'volume'),
        (indicators.sma, 100, 'sma100v', 'volume'),
        (indicators.ema, 10, 'ema10c'),
        (indicators.ema, 20, 'ema20c'),
        (indicators.ema, 30, 'ema30c'),
        (indicators.ema, 40, 'ema40c'),
        (indicators.ema, 50, 'ema50c'),
        (indicators.ema, 100, 'ema100c'),
        (indicators.ema, 10, 'ema10v', 'volume'),
        (indicators.ema, 20, 'ema20v', 'volume'),
        (indicators.ema, 30, 'ema30v', 'volume'),
        (indicators.ema, 40, 'ema40v', 'volume'),
        (indicators.ema, 50, 'ema50v', 'volume'),
        (indicators.ema, 100, 'ema100v', 'volume'),
    ]

    for indicator in indicator_list:
        func = indicator[0]
        args = indicator[1:]
        func(dataset, *args)

    dataset.dropna(axis=0, inplace=True)
    dataset = dataset.reset_index(drop=True)
    return dataset


def strat(row):
    pass


def backtest():
    
    # prepare data, based on saved data, or refresh and save
    data = load('BTC-EUR', '1h')
    if not len(data):
        api = provider.BitvavoRestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])
        data = api.get_data(market='BTC-EUR', interval='1h', number=40)
        save(data, 'BTC-EUR', '1h')
    
    # set up test environment
    api = provider.TestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'], data=data, balance={'EUR': 1000})
    
    # step through test data
    step = True
    while step:
        step = api.step()
        data = api.get_data()
        dataset = to_dataset(data)
        dataset = apply_indicators(dataset)
        print(dataset.iloc[-1].date, end='\r')
    print()



def test():
    api = provider.BitvavoRestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])
    api.DEBUG = True


    # status
    print('--status--')
    eur = float(api.balance(symbol='EUR')[0]['available'])
    print(f'{eur=}')
    btc = float(api.balance(symbol='BTC')[0]['available'])
    print(f'{btc=}')


    # buy
    print('--buy--')
    result = api.place_order(market='BTC-EUR', side='BUY', order_type='market', amountQuote=eur)
    print(result)
    result = api.place_order(market='BTC-EUR', side='SELL', order_type='market', amount=btc)
    print(result)

    provider.time.sleep(5)

    # status
    print('--status--')
    eur = float(api.balance('EUR')[0]['available'])
    print(f'{eur=}')
    btc = float(api.balance('BTC')[0]['available'])
    print(f'{btc=}')
    trades = api.get_trades(market='BTC-EUR')[0]
    print(f'{trades=}')




if __name__ == '__main__':
    if '--test' in sys.argv: test()
    if '--backtest' in sys.argv: backtest()
    if '--dev' in sys.argv:
        api = provider.BitvavoRestClient(api_key=provider.settings()['key'], api_secret=provider.settings()['secret'])
        breakpoint()
