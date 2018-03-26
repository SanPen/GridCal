import time
import threading
import multiprocessing

def func():
    result = 0
    for i in range(10**7):
        result += i

num_jobs = 10


# 1. measure, how long it takes 10 consistent func() executions
t = time.time()
for _ in range(num_jobs):
    func()
print ("10 consistent func executions takes:\n{:.2f} seconds\n".format(time.time() - t))

# 2. threading module, 10 jobs
jobs = []
for _ in range(num_jobs):
    jobs.append(threading.Thread(target = func, args=()))
t = time.time()
for job in jobs:
    job.start()
for job in jobs:
    job.join()
print ("10 func executions in parallel (threading module) takes:\n{:.2f} seconds\n".format(time.time() - t))

# 3. multiprocessing module, 10 jobs
jobs = []
for _ in range(num_jobs):
    jobs.append(multiprocessing.Process(target=func, args=()))
t = time.time()
for job in jobs:
    job.start()
for job in jobs:
    job.join()
print ("10  func executions in parallel (multiprocessing module) takes:\n{:.2f} seconds\n".format(time.time() - t))