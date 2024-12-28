import os
import indicators
import provider


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


def test():
    api = provider.BitvavoRestClient(provider.settings()['key'], provider.settings()['secret'])
    api.DEBUG = True
    data = api.get_data('BTC-EUR', '1h', number=40)
    api = provider.TestClient(data, {'EUR': 1000})
    
    step = True
    while step:
        step = api.step()
        data = api.get_data()
        dataset = provider.to_dataset(data)
        dataset = apply_indicators(dataset)
        print(dataset.iloc[-1].date, end='\r')
    print()




if __name__ == '__main__':
    test()


    # if window.iloc[0].hasnans: continue
