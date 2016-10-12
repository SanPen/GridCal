from PyQt5.QtCore import QThreadPool, QRunnable


class SomeObjectToDoComplicatedStuff(QRunnable):
    def __init__(self, name):
        QRunnable.__init__(self)
        self.name = name

    def run(self):
        print('running', self.name)
        a = 10
        b = 30
        c = 0
        for i in range(5000000):
            c += a**b
        print('done', self.name)


pool = QThreadPool.globalInstance()
pool.setMaxThreadCount(10)

batch_size = 100

workers = [None] * batch_size

for i in range(batch_size):
    worker = SomeObjectToDoComplicatedStuff('object ' + str(i))
    workers[i] = worker
    pool.start(worker)

print('All cued')
pool.waitForDone()

# processing the results back
for i in range(batch_size):
    print(workers[i].name, ' - examining again.')
