import numpy as np


# helper function
def calculate_sma(data, period):
    result = np.empty((len(data), 1,))
    result[:] = np.nan

    for n in range(len(data)):
        if period > n: continue
        result[n, 0] = data[n-period:n].sum() / period
    
    return result


# helper function
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
