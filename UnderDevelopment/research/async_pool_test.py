from multiprocessing import Pool
from time import sleep
from random import randint
import os


class AsyncFactory:

    def __init__(self, func):
        self.func = func
        self.pool = Pool()
        self.results = list()

    def call(self, *args, **kwargs):

        def collect(res):
            self.results.append(res)

        self.pool.apply_async(self.func, args, kwargs, collect)

    def wait(self):
        self.pool.close()
        self.pool.join()


def square(x1, x2):
    # sleep_duration = randint(1, 5)
    # print("PID: %d \t Value: %d" % (os.getpid(), x))
    # sleep(sleep_duration)
    return x1 * x2


async_square = AsyncFactory(square)

for i in range(1000):
    async_square.call(i, i+2)

async_square.wait()

print(async_square.results)
