import random


def to_function(chromosome: list = [], template: str = '{}'):
    function = ''
    while chromosome:
        left = int(''.join(map(str, chromosome[:8])), 2)
        operator = ['>', '<', '==', '!='][int(''.join(map(str, chromosome[8:10])), 2)]
        right = int(''.join(map(str, chromosome[10:18])), 2)
        
        left = template.format(left)
        right = template.format(right)

        function += f'({left}{operator}{right})'
        for _ in range(18): chromosome.pop(0)
        if len(chromosome):
            function += ['&', '|'][int(str(chromosome[0]), 2)]
            chromosome.pop(0)
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




def Incubator():
    def __init__(self, api):
        self.api = api
        self.population = new_population(400, 10)

    def develop(self):
        pass
    
    def step(self):
        
        pass


