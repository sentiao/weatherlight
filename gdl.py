import random


SELECT_BEST = 1
SELECT_WORST = -1


def to_function(chromosome: list = [], template: str = '{}'):
    function = ''
    n = 0
    while True:
        left = int(''.join(map(str, chromosome[:8+n])), 2)
        operator = ['>', '<', '==', '!='][int(''.join(map(str, chromosome[8+n:10+n])), 2)]
        right = int(''.join(map(str, chromosome[10+n:18+n])), 2)
        
        left = template.format(left)
        right = template.format(right)

        function += f'({left}{operator}{right})'
        n += 18
        if len(chromosome) > n:
            function += ['&', '|'][int(str(chromosome[n]), 2)]
            n += 1
        else:
            break

    return function


def new_chromosome(length):
    # 8-bit number for ID
    # 2 bit operator (> < >= <=)
    # 1 bit separator (| &)
    return [random.randint(0,1) for _ in range(8+2+8+1) for _ in range(length)][:-1]


def new_population(size, chromosome_length):
    return [new_chromosome(chromosome_length) for _ in range(size)]


def crossover(candidates):
    length = len(candidates[0])
    result = [random.choice([c[n] for c in candidates]) for n in range(length)]
    return result


def select(population, fitness, number, mode):
    total = sum(fitness)
    if mode == SELECT_BEST:
        probabilities = [f / total for f in fitness]
    if mode == SELECT_WORST:
        probabilities = [total / f for f in fitness]
    candidates = [random.choices(population, probabilities)[0] for _ in range(number)]
    return candidates


class Incubator():
    def __init__(self, size: int, length: int, api_init, api_args: dict):
        self.size = size
        self.length = length
        self.api_init = api_init
        self.api_args = api_args
        self.data = None
        self.balance = None
        self.population = []
    
    def reset(self):
        for ind in self.population:
            ind['api'].n = -1
            ind['perf'] = 0.0

    def init(self, data, balance):
        self.data = data
        self.balance = balance
        self.population = []
        for _ in range(self.size):
            self.add_individual()
    
    def add_individual(self, buy=None, sell=None):
        if not buy: buy = new_chromosome(self.length)
        if not sell: sell = new_chromosome(self.length)

        self.population.append({
            'api': self.api_init(**{**{'data':self.data, 'balance': self.balance}, **self.api_args}),
            'perf': 0.0,
            'buy': buy,
            'sell': sell,
        })

    def develop(self):
        market = 'ETH-EUR'
        symbol, quote = market.split('-')
        step = True
        s = -1
        while step:
            s += 1
            print(f'{s}', end='\r')
            step = self.population[0]['api'].step()
            data = self.population[0]['api'].get_data()
            len_data = len(data.iloc[0].iloc[5:])

            self.performance = [0.0 for _ in range(self.size)]
            #for n in range(self.size):
            for ind in self.population:
                value = ind['api'].net_worth(symbol)
                eur = float(ind['api'].get_balance(symbol='EUR')[0]['available'])
                sym = float(ind['api'].get_balance(symbol=symbol)[0]['available'])
                
                template = 'data.iloc[0].iloc[5:].iloc[{}%' + str(len_data) + ']'
                buy_signal = eval(to_function(ind['buy'], template)) 
                sell_signal = eval(to_function(ind['sell'], template))

                buy_signal = buy_signal & (sym == 0) & (eur > 10)
                sell_signal = sell_signal & (sym != 0)

                if buy_signal and sell_signal: buy_signal = False

                if buy_signal:
                    result = ind['api'].place_order(market=market, side='buy', order_type='market', amountQuote=eur)
                if sell_signal:
                    result = ind['api'].place_order(market=market, side='sell', order_type='market', amount=sym)

                ind['perf'] = ind['perf'] + ((ind['api'].net_worth(symbol) / value))
            


        candidates = select(self.population, [can['perf'] for can in self.population], int(self.size/2), SELECT_WORST)
        for can in candidates:
            try:
                self.population.remove(can)
            except:
                pass

        candidates = select(self.population, [can['perf'] for can in self.population], int((self.size - len(self.population)) / 2), SELECT_BEST)
        for n in range(int((self.size - len(self.population)) / 2)):
            buy = crossover([can['buy'] for can in candidates])
            sell = crossover([can['sell'] for can in candidates])
            self.add_individual(buy=buy, sell=sell)
        for n in range(self.size - len(self.population)):
            self.add_individual(buy=buy, sell=sell)

