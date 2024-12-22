
def candle(data):
    if data.open == data.high == data.close == data.low:
        ratio = 0.0
    else:
        hl = sorted([data.high, data.low])
        oc = sorted([data.open, data.close])
        ratio = (oc[1]-oc[0]) / (hl[1]-hl[0])
        if data.open > data.close: ratio *= -1.0
    
    return ratio


def sma(data, period, name='', column='close'):
    name = name or f'SMA_{period}'
    data[name] = data[column].rolling(period).mean()


def ema(data, period, name='', column='close'):
    name = name or f'EMA_{period}'
    data[name] = data[column].ewm(period, adjust=False).mean()


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


def rsi(data, period, name='', column='close'):
    name = name or f'RSI_{period}'
    up = data[column].diff().clip(lower=0).abs()
    ema_up = up.ewm(com=period, adjust=False).mean()
    down = data[column].diff().clip(upper=0).abs()
    ema_down = down.ewm(com=period, adjust=False).mean()
    rs = ema_up / ema_down
    data[name] = 100 - (100 / (1 + rs))


def atr(data, period, name='', column='close'):
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