import os
import requests
import hashlib
import hmac
import time
from datetime import datetime
import numpy as np


API_LIMIT_MINIMUM = 100


def to_date(timestamp):
    return datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')


class RestClient:
    def __init__(self, api_key: str, api_secret: str, access_window: int = 10000):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_window = access_window
        self.base = 'https://api.bitvavo.com/v2'
        self.limit = 0

    def place_order(self, market: str, side: str, order_type: str, amount: float | None = None, amountQuote: float | None = None):
        """
        Send an instruction to Bitvavo to buy or sell a quantity of digital assets at a specific price.
        :param market: the market to place the order for. For example, `BTC-EUR`.
        :param side: either 'buy' or 'sell' in `market`.
        :param order_type: the character of the order. For example, a `stopLoss` order type is an instruction to
                           buy or sell a digital asset in `market` when it reaches the price set in `body`.
        """
        body = {
            'market': market,
            'side': side,
            'orderType': order_type
        }
        
        if amount: body['amount'] = str(amount)
        if amountQuote: body['amountQuote'] = str(amountQuote)

        return self.__request(method='POST', endpoint='/order', body=body)

    def get_trades(self, market: str = ''):
        return self.__request(endpoint=f'/trades?market={market}', method='GET')

    def get_balance(self, symbol: str = ''):
        if symbol:
            return self.__request(endpoint=f'/balance?symbol={symbol}', method='GET')
        else:
            return self.__request(endpoint=f'/balance', method='GET')

    def get_data(self, markets, interval, amount=1440, number=1):
        main_market = markets[0]
        data = None
        for market in markets:
            new_data = self.get_market(market, interval, amount, number)
            if market == main_market:
                data = new_data.copy()
                continue

            n = new_data.shape[1] - 1
            col = np.empty((len(data), n,))
            col[:] = np.nan
            data = np.c_[data, col]            

            for date in data[:, 0]:
                match = data[:, 0] == date
                match_new = new_data[:, 0] == date

                match = np.where(match)[0]
                match_new = np.where(match_new)[0]

                if not len(match): continue # this should never happen
                if not len(match_new): continue # not found
                
                r = match[0]
                r_new = match_new[0]

                data[r, 0-n:] = new_data[r_new, 1:]
        
        return data[:-1]

    def get_market(self, market, interval, amount=1440, number=1):
        if number == -1: number = 999999
        h_start, h_end = 0, 0
        
        data = np.array([])
        for n in range(number):
            if len(data):
                end = int(data[-1][0])
                start = int(end - (24*60*60*60*999))
                if start == h_start and end == h_end: break
                h_start, h_end = start, end
                response = self.__request(endpoint=f'/{market}/candles?interval={interval}&limit={amount}&start={start}&end={end}', method='GET')
            else:
                response = self.__request(endpoint=f'/{market}/candles?interval={interval}&limit={amount}', method='GET')
            
            new_data = np.array(response).astype(float)
            if len(data):
                data = np.concatenate((data, new_data))
            else:
                data = new_data

        data = np.unique(data, axis=0)
        data = data[data[:, 0].argsort()]
        
        return data[:-1]

    def __request(self, endpoint: str, body: dict | None = None, method: str = 'GET'):
        """
        Create the headers to authenticate your request, then make the call to Bitvavo API.
        :param endpoint: the endpoint you are calling. For example, `/order`.
        :param body: for GET requests, this can be an empty string. For all other methods, a string
                     representation of the call body.
        :param method: the HTTP method of the request.
        """
        print(f'____       {method} {self.base}{endpoint}', end='')
        now = int(time.time() * 1000)
        sig = self.__signature(now, method, endpoint, body)
        url = self.base + endpoint
        headers = {
            'bitvavo-access-key': self.api_key,
            'bitvavo-access-signature': sig,
            'bitvavo-access-timestamp': str(now),
            'bitvavo-access-window': str(self.access_window),
        }
        response = requests.request(method=method, url=url, headers=headers, json=body)
        
        if 'bitvavo-ratelimit-remaining' in response.headers:
            self.limit = int(response.headers['bitvavo-ratelimit-remaining'])
        print(f'\r{self.limit:04d}   ', end='')
        if API_LIMIT_MINIMUM > self.limit:
            print(f'\r{self.limit:04d} * ', end='')
            time.sleep(60)

        print(response.status_code)

        if response.status_code == 200:
            return response.json()
        else:
            print(f'[ERROR] {response.json()}', end='')
        
        print()

    def __signature(self, timestamp: int, method: str, url: str, body: dict | None):
        """
        Create a hashed code to authenticate requests to Bitvavo API.
        :param timestamp: a unix timestamp showing the current time.
        :param method: the HTTP method of the request.
        :param url: the endpoint you are calling. For example, `/order`.
        :param body: for GET requests, this can be an empty string. For all other methods, a string
                     representation of the call body. For example, for a call to `/order`:
                     `{"market":"BTC-EUR","side":"buy","price":"5000","amount":"1.23", "orderType":"limit"}`.
        """
        string = str(timestamp) + method + '/v2' + url
        if (body is not None) and (len(body.keys()) != 0):
            string += '{' + ','.join([f'"{k}":"{v}"' for k, v in body.items()]) + '}'
        signature = hmac.new(self.api_secret.encode('utf-8'), string.encode('utf-8'), hashlib.sha256).hexdigest()
        return signature


class TestClient(RestClient):
    def __init__(self, api_key: str = '', api_secret: str = '', access_window: int = 10000, balance = {}):
        super().__init__(api_key, api_secret, access_window)
        self.balance = balance
        self.trades = []
        self.data = None
        self.current = None

    def place_order(self, market: str, side: str, order_type: str, amount: float | None = None, amountQuote: float | None = None):
        now = str(int(time.time() * 1000))

        symbol, quote = market.split('-')
        price = self.current[-1, 4] # close

        if side == 'buy':
            fee = amountQuote * 0.0025
            amount = (amountQuote - fee) / price

            self.balance[quote] = self.balance.get(quote, 0) - amountQuote
            self.balance[symbol] = self.balance.get(symbol, 0) + amount

        if side == 'sell':
            amountQuote = amount * price
            fee = amountQuote * 0.0025
            amountQuote -= fee

            self.balance[symbol] = self.balance.get(symbol, 0) - amount
            self.balance[quote] = self.balance.get(quote, 0) + amountQuote

        trade = {
            'timestamp': now,
            'side': side,
            'market': market,
            'amount': amount,
            'price': price,
            'fee': fee,
        }
        self.trades = [trade] + self.trades
        return trade

    def get_trades(self, market: str = ''):
        trades = []
        for trade in self.trades:
            if market and not trade['market'] == market: continue
            trades.append(trade)
        return trades

    def get_balance(self, symbol: str = ''):
        balances = [{'symbol': symbol, 'available': amount} for symbol, amount in self.balance.items()]
        if symbol:
            for balance in balances:
                if balance['symbol'] == symbol: return [balance]
            else:
                self.balance[symbol] = 0
                return [{'symbol': symbol, 'available': 0}]
        else:
            return balances

    def get_data(self, *args, **kwargs):
        return self.current

    def set_data(self, data = None):
        self.data = data
    
    def set_balance(self, balance = {}):
        self.balance = balance

    def step(self, counter, window_size):
        if (counter + window_size) >= len(self.data):
            return counter, False
        else:
            counter += 1
            self.current = self.data[counter : counter + window_size, :]
            return counter, True

    def net_worth(self, symbol):
        return float(self.current[-1, 4] * float(self.get_balance(symbol=symbol)[0]['available'])) + float(self.get_balance(symbol='EUR')[0]['available'])

    def training_worth(self, symbol):
        return float(self.current[-1, 4] * 0.5 * float(self.get_balance(symbol=symbol)[0]['available'])) + float(self.get_balance(symbol='EUR')[0]['available'])
