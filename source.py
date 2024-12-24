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


with open('../settings.json', 'r') as fh: settings = json.load(fh)
API_LIMIT_MINIMUM = 100


class BitvavoRestClient:
    def __init__(self, api_key: str, api_secret: str, access_window: int = 10000):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_window = access_window
        self.base = 'https://api.bitvavo.com/v2'
        self.limit = 0
        self.private_limit = 1000
        self.public_limit = 1000

    def update_limit(self, response):
        limit = 0
        if 'error' in response.json():
            response = response.json()
        else:
            response = response.headers

        if 'errorCode' in response:
            self.limit = 0
        if 'bitvavo-ratelimit-remaining' in response:
            self.limit = int(response['bitvavo-ratelimit-remaining'])
        
        print(f'limit ({type}) = {self.limit}')
        if API_LIMIT_MINIMUM > self.limit:
            print(f'{type}_limit={self.limit} >> waiting 60s')
            time.sleep(60)

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
        return self.request(method='POST', endpoint='/order', body=body)

    def balance(self, symbol: str):
        return self.request(endpoint=f'/balance?symbol={symbol}', method='GET')

    def get_candles(self, market, interval, number=1, data=np.array([])):
        start, end = 0, 0
        diff = (24*60*60*60)*999

        if len(data):
            end = data[0][0]
            start = end - diff

        for n in range(number):
            if start != 0 and end != 0:
                response = self.request(endpoint=f'/{market}/candles?interval={interval}&start={start}&end={end}', method='GET')
            else:
                response = self.request(endpoint=f'/{market}/candles?interval={interval}', method='GET')
            
            response.reverse()
            new_data = np.array(response).astype(float)
            if data.size > 0: data = np.concatenate((new_data, data))
            else: data = new_data
            data = np.unique(data, axis=0)
            data = data[data[:, 0].argsort()]
            end = new_data[0][0]
            start = end - diff
        
        return data

    def request(self, endpoint: str, body: dict | None = None, method: str = 'GET'):
        """
        Create the headers to authenticate your request, then make the call to Bitvavo API.
        :param endpoint: the endpoint you are calling. For example, `/order`.
        :param body: for GET requests, this can be an empty string. For all other methods, a string
                     representation of the call body.
        :param method: the HTTP method of the request.
        """
        print(f'{method} {self.base}{endpoint}')
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
        self.update_limit(response)
        if response.status_code == 200:
            return response.json()

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


def to_dataset(data):
    data = pd.DataFrame(data, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
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