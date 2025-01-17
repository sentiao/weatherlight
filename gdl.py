import os
import random
import provider
from multiprocessing import Pool, Process, Value, Array
from copy import deepcopy


LOG = True


ENABLER = 1
NUMBER = 8
OPERATOR = 2
SEPARATOR = 1
OPERATOR_MAP = ('==', '!=', '>', '<')
SEPARATOR_MAP = ('|', '&')

GENE = ENABLER + NUMBER + NUMBER + OPERATOR + NUMBER + NUMBER + SEPARATOR


def to_function(gene: str, template: str = '__number__'):
    f = 0.015748031496062992
    function = ''
    n = 0
    while True:
        if n >= len(gene) - 1: break

        enabled = bool(int(gene[n:n + ENABLER], 2))
        n += ENABLER

        if not enabled:
            n += (GENE - ENABLER)
            continue

        value_or_ref = bool(int(gene[n], 2))
        left = str(int(gene[n + 1:n + NUMBER], 2))
        if value_or_ref: left = template.replace('__number__', left)
        n += NUMBER

        enabled = bool(int(gene[n], 2))
        left_factor = str((int(gene[n + 1:n + NUMBER], 2) - 63.5) * f)
        if enabled: left += f'*{left_factor}'
        n += NUMBER

        operator = OPERATOR_MAP[int(gene[n:n + OPERATOR], 2)]
        n += OPERATOR

        value_or_ref = bool(int(gene[n], 2))
        right = str(int(gene[n + 1:n + NUMBER], 2))
        if value_or_ref: right = template.replace('__number__', right)
        n += NUMBER

        enabled = bool(int(gene[n], 2))
        right_factor = str((int(gene[n + 1:n + NUMBER], 2) - 63.5) * f)
        if enabled: right += f'*{right_factor}'
        n += NUMBER


        function += f'(({left}){operator}({right})){SEPARATOR_MAP[int(gene[n:n + SEPARATOR], 2)]}'
        n += SEPARATOR
        
    
    function = function[:-1]
    if not function: function = 'False'

    return function


def new_gene(gene_size):
    return ''.join([str(random.randint(0,1)) for _ in range(GENE) for _ in range(gene_size)])


def mutate(gene, rate):
    subject = list(gene)
    for n in range(len(subject)):
        if random.random() < rate:
            subject[n] = {'0':'1', '1':'0'}[subject[n]]
    return ''.join(subject)


def dbz(left, right):
    try:
        return left / right
    except ZeroDivisionError:
        return 0


def select_simple(population, number, mode):
    if mode == 'best':
        return sorted(population, key=lambda n: n['perf'])[0-number:]

    if mode == 'worst':
        return sorted(population, key=lambda n: n['perf'])[0:number]

def select(population, number, mode):
    if mode == 'best':
        probabilities = [p['perf'] / len(population) for p in population]
    if mode == 'worst':
        probabilities = [dbz(len(population), p['perf']) for p in population]
    candidates = [random.choices(population, probabilities)[0] for _ in range(number)]

    return candidates


class Incubator():
    def __init__(self, api_class: provider.MultiTestClient, market: str, population_size : int, gene_size : int, mutation_rate : int):
        self.api_class = api_class
        self.market = market
        self.population_size = population_size
        self.gene_size = gene_size
        self.mutation_rate = mutation_rate
        self.wallet_start = 1000.0

        self.population = []
        for _ in range(self.population_size):
            self.population.append({
                'api': self.api_class(balance={'EUR': 1000.0}),
                'buy': new_gene(self.gene_size),
                'sell': new_gene(self.gene_size),
                'perf': 0.0,
            })

    def set_data(self, data):
        self.data = data
        api = self.api_class()
        api.set_data(data=self.data)
    
    def run(self):
        symbol, quote = self.market.split('-')
        row_length = len(self.data.iloc[-1][5:])
        template = f'data.iloc[-1].iloc[5:].iloc[__number__ % {row_length}]'

        api = self.api_class()
        for node in self.population: node['api'].set_balance({'EUR': self.wallet_start})
        
        step_counter, step = -1, True
        while step:
            step_counter, step = api.step(step_counter, 1)
            data = api.get_data()
            
            for node in self.population:

                for trade in node['api'].get_trades(self.market):
                    if trade.get('side', '') != 'buy': continue
                    history = trade.get('price', 0.0)
                    break
                else:
                    history = 0.0
                
                quo = node['api'].get_balance(quote)[0]['available']
                sym = node['api'].get_balance(symbol)[0]['available']

                buy = to_function(gene=node['buy'], template=template)
                sell = to_function(gene=node['sell'], template=template)

                node['buy_function'] = buy
                node['sell_function'] = sell
                
                buy_signal = eval(buy) & (sym == 0) & (quo > 10)
                sell_signal = (sym != 0) & (history * 0.95 > data.iloc[-1].close) | eval(sell)
                
                if buy_signal and sell_signal: sell_signal = False

                quo = float(node['api'].get_balance(symbol=quote)[0]['available'])
                sym = float(node['api'].get_balance(symbol=symbol)[0]['available'])

                if buy_signal:
                    result = node['api'].place_order(market=self.market, side='buy', order_type='market', amountQuote=quo)
                if sell_signal:
                    result = node['api'].place_order(market=self.market, side='sell', order_type='market', amount=sym)
                
                node['perf'] = node['api'].net_worth(symbol)
                
            if LOG: print(f'{api.get_data().iloc[-1].Date:19s}', end='\r')
        
        
        # penalize passives
        for node in self.population:
            if node['perf'] == self.wallet_start: node['perf'] = self.wallet_start / 2

        # select absolute best, to report and return
        best = select_simple(self.population, 1, 'best')[0]
        fn = 'C:/Temp/best.txt'
        if not os.path.exists(fn):
            with open(fn, 'w') as fh: fh.write('perf,buy,sell\n')
        with open(fn, 'a') as fh:
            fh.write(f'{best["perf"]}, {best["buy_function"]}, {best["sell_function"]}\n')

        # remove unhealthy third
        while len(self.population) > int(self.population_size / 3):
            self.population.remove(select_simple(self.population, 1, 'worst')[0])  

        # select most healthy third
        candidates = select(self.population, int(self.population_size / 2) or 1, 'best')

        while self.population_size > len(self.population):
            self.population.append({ # Random Node
                'api': self.api_class(balance={'EUR': self.wallet_start}),
                'buy': new_gene(self.gene_size),
                'sell': new_gene(self.gene_size),
                'perf': 0.0,
            })

            mother, father = random.sample(candidates, 2)
            self.population.append({ # Mutated Node
                'api': self.api_class(balance={'EUR': self.wallet_start}),
                'buy': father['buy'],
                'sell': mother['sell'],
                'perf': 0.0,
            })
            
            mother, father = random.sample(candidates, 2)
            self.population.append({ # Mutated Node
                'api': self.api_class(balance={'EUR': self.wallet_start}),
                'buy': mutate(father['buy'], self.mutation_rate),
                'sell': mutate(mother['sell'], self.mutation_rate),
                'perf': 0.0,
            })

        # remove overpopulation
        while len(self.population) > self.population_size:
            self.population.remove(select(self.population, 1, 'worst')[0])
        
        if LOG: print(f'{best["perf"]=}')

        return to_function(gene=best['buy'], template=template), to_function(gene=best['sell'], template=template)
