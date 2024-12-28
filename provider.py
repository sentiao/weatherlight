import os
import requests
import json
import hashlib
import hmac
import time
from datetime import datetime
import pickle
import numpy as np
import pandas as pd


API_LIMIT_MINIMUM = 100


def settings():
    with open('../settings.json', 'r') as fh:
        return json.load(fh)


class BitvavoRestClient:
    def __init__(self, api_key: str, api_secret: str, access_window: int = 10000):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_window = access_window
        self.base = 'https://api.bitvavo.com/v2'
        self.limit = 0
        self.DEBUG = False

    def place_order(self, market: str, side: str, order_type: str, amount: float):
        """
        Send an instruction to Bitvavo to buy or sell a quantity of digital assets at a specific price.
        :param market: the market to place the order for. For example, `BTC-EUR`.
        :param side: either 'buy' or 'sell' in `market`.
        :param order_type: the character of the order. For example, a `stopLoss` order type is an instruction to
                           buy or sell a digital asset in `market` when it reaches the price set in `body`.
        :param body: the parameters for the call. For example, {'amount': '0.1', 'price': '2000'}.
        """
        body = {
            'market': market,
            'side': side,
            'orderType': order_type,
            'amount': amount
        }
        return self.__request(method='POST', endpoint='/order', body=body)

    def balance(self, symbol: str = ''):
        if symbol:
            return self.__request(endpoint=f'/balance?symbol={symbol}', method='GET')
        else:
            return self.__request(endpoint=f'/balance', method='GET')

    def get_data(self, market, interval, amount=1440, number=1, data=np.array([])):

        for n in range(number):
            if len(data):
                end = data[0][0]
                start = end - (24*60*60*60*999)
                response = self.__request(endpoint=f'/{market}/candles?interval={interval}&limit={amount}&start={start}&end={end}', method='GET')
            else:
                response = self.__request(endpoint=f'/{market}/candles?interval={interval}&limit={amount}', method='GET')
            
            response.reverse()
            new_data = np.array(response).astype(float)
            if data.size > 0: data = np.concatenate((new_data, data))
            else: data = new_data
            data = np.unique(data, axis=0)
            data = data[data[:, 0].argsort()]
        
        return data

    def __request(self, endpoint: str, body: dict | None = None, method: str = 'GET'):
        """
        Create the headers to authenticate your request, then make the call to Bitvavo API.
        :param endpoint: the endpoint you are calling. For example, `/order`.
        :param body: for GET requests, this can be an empty string. For all other methods, a string
                     representation of the call body.
        :param method: the HTTP method of the request.
        """
        if self.DEBUG: print(f'{method} {self.base}{endpoint}')
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
        if self.DEBUG: print(f'limit={self.limit}')
        if API_LIMIT_MINIMUM > self.limit:
            print(f'limit={self.limit} >> waiting 60s')
            time.sleep(60)

        if response.status_code == 200:
            return response.json()
        else:
            print(f'error {response.status_code}: {response.json()}')

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


class TestClient(BitvavoRestClient):
    def __init__(self, data, balance={}):
        self.DEBUG = False
        self.data = data
        self.balance = balance
        self.n = -1
        self.current = None

    def place_order(self, market: str, side: str, order_type: str, amount: float):
        pass

    def balance(self, symbol: str = ''):
        if symbol: return self.balance.get(symbol)
        else: return self.balance

    def get_data(self):
        return self.current

    def step(self):
        if self.n+1440 > len(self.data) - 2:
            return False
        else:
            self.n += 1
            self.current = self.data[:-1][self.n:self.n+1440]
            return True


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
