import json
import f
import source


def apply_indicators(dataset):
    indicators = [
        (f.sma, 10, 'sma10c'),
        (f.sma, 20, 'sma20c'),
        (f.sma, 30, 'sma30c'),
        (f.sma, 40, 'sma40c'),
        (f.sma, 50, 'sma50c'),
        (f.sma, 100, 'sma100c'),
        (f.sma, 10, 'sma10v', 'volume'),
        (f.sma, 20, 'sma20v', 'volume'),
        (f.sma, 30, 'sma30v', 'volume'),
        (f.sma, 40, 'sma40v', 'volume'),
        (f.sma, 50, 'sma50v', 'volume'),
        (f.sma, 100, 'sma100v', 'volume'),
        (f.ema, 10, 'ema10c'),
        (f.ema, 20, 'ema20c'),
        (f.ema, 30, 'ema30c'),
        (f.ema, 40, 'ema40c'),
        (f.ema, 50, 'ema50c'),
        (f.ema, 100, 'ema100c'),
        (f.ema, 10, 'ema10v', 'volume'),
        (f.ema, 20, 'ema20v', 'volume'),
        (f.ema, 30, 'ema30v', 'volume'),
        (f.ema, 40, 'ema40v', 'volume'),
        (f.ema, 50, 'ema50v', 'volume'),
        (f.ema, 100, 'ema100v', 'volume'),
    ]

    for indicator in indicators:
        func = indicator[0]
        args = indicator[1:]
        func(dataset, *args)
    return dataset


with open('../settings.json', 'r') as fh: settings = json.load(fh)
api = source.BitvavoRestClient(settings['key'], settings['secret'])

data = source.get_candles(api, 'BTC-EUR', '1h')
data = source.get_candles(api, 'BTC-EUR', '1h', 1, data)

dataset = source.to_dataset(data)
apply_indicators(dataset)
print(dataset)