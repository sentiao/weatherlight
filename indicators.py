import numpy as np

def candle(data):
    if data.open == data.high == data.close == data.low:
        ratio = 0.0
    else:
        hl = sorted([data.high, data.low])
        oc = sorted([data.open, data.close])
        ratio = (oc[1]-oc[0]) / (hl[1]-hl[0])
        if data.open > data.close: ratio *= -1.0
    
    return ratio


def calculate_sma(data, period):
    result = np.empty((len(data), 1,))
    result[:] = np.nan

    for n in range(len(data)):
        if period > n: continue
        result[n, 0] = data[n-period:n].sum() / period
    
    return result


def calculate_ema(data, period):
    result = np.empty((len(data), 1,))
    result[:] = np.nan

    for n in range(len(data)):
        if data[n] == np.nan: continue
        if data[n-1] == np.nan: continue

        p = data[n]
        a = 2 / (1 + period)

        result[n] = (p * a) + (result[n-1] * (1 - a))
    
    return result


def sma(data, period, column=4):
    _sma = calculate_sma(data[:, column], period)
    return np.c_[data, _sma]


def ema(data, period, column=4):
    _sma = calculate_sma(data[:, column], period)
    _ema = calculate_ema(_sma, period)
    return np.c_[data, _sma]



def rsi(data, period, column=4): # this one first
    up = np.empty((len(data), 1,))
    up[:] = 0.0
    down = np.empty((len(data), 1,))
    down[:] = 0.0

    for n in range(len(data)):
        if n == 0: continue
        current, previous = data[n, column], data[n-1, column]
        if current == previous: continue
        if current > previous:
            up[n, 0] = current - previous
        if previous > current:
            down[n, 0] = previous - current
    
    _rsi = np.empty((len(data), 1,))
    _rsi[:] = np.nan
    for n in range(len(data)):
        if period > n: continue
        ma_up = up[n-period:n, 0].sum() / period
        ma_down = down[n-period:n, 0].sum() / period
        if ma_down == 0: rs = ma_up
        else: rs = ma_up / ma_down
        _rsi[n, 0] = 100 - (100 / (1 + rs))

    return np.c_[data, _rsi]


def rsi(data, period, column=4):
    result = np.empty((len(data), 1,))
    result[:] = np.nan

    diff_up = np.array([0.0] * len(data))
    diff_down = np.array([0.0] * len(data))
    for n in range(len(data)):
        if n == 0: continue
        diff = data[n, column] - data[n-1, column]
        if diff > 0: diff_up[n] = abs(diff)
        if 0 > diff: diff_down[n] = abs(diff)
    
    for n in range(len(data)):
        if period > n: continue
        mean_up = diff_up[n-period:n].mean()
        mean_down = diff_down[n-period:n].mean()

        if mean_down == 0.0:
            rs = mean_up
        else:
            rs = mean_up / mean_down
        
        result[n] = 100 - (100 / (1 + rs))
    
    return np.c_[data, result]


def macd(data, fast, slow, signal):
    k = data.close.ewm(span=fast, adjust=False, min_periods=fast).mean()
    d = data.close.ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd = k - d
    macd_signal = macd.ewm(span=signal, adjust=False, min_periods=signal).mean()
    macd_histogram = macd - macd_signal
    data['MACD'] = macd
    data['MACD_SIGNAL'] = macd_signal
    data['MACD_HISTOGRAM'] = macd_histogram


def hour(data):
    d = lambda n: int(n.split(' ')[-1].split(':')[0])
    data['HOUR'] = data.date.apply(d)


def minute(data):
    d = lambda n: int(n.split(' ')[-1].split(':')[1])
    data['MINUTE'] = data.date.apply(d)



def atr(data, period, name='', column='close'): # this one
    name = name or f'ATR_{period}'
    tr_list = []
    for i in range(len(data)):
        high = data.high.iloc[i]
        low = data.low.iloc[i]
        if i > 0:
            prev_close = data.close.iloc[i-1]
        else:
            prev_close = 0
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)

    atr_list = []
    for i in range(len(data)):
        if i < period:
            atr = sum(tr_list[:i+1]) / (i+1)
        else:
            atr = sum(tr_list[i-period+1:i+1]) / period
        atr_list.append(atr)

    data[name] = atr_list
    return data