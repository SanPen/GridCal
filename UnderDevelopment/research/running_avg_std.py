import math
from numpy import zeros_like, random
from matplotlib import pyplot as plt


def statsnp(x):
  n = 0
  S = 0.0
  m = 0.0
  Sarr = zeros_like(x)
  Marr = zeros_like(x)
  for x_i in x:
    n += 1
    m_prev = m
    m += (x_i - m) / n
    S += (x_i - m) * (x_i - m_prev)
    Marr[n-1] = m
    Sarr[n-1] = S/n

  return Marr, Sarr


def stats(x):
  n = 0
  S = 0.0
  m = 0.0
  for x_i in x:
    n += 1
    m_prev = m
    m += (x_i - m) / n
    S += (x_i - m) * (x_i - m_prev)
  return {'mean': m, 'variance': S/n}


def naive_stats(x):
  S1 = sum(x)
  n = len(x)
  S2 = sum([x_i**2 for x_i in x])
  return {'mean': S1/n, 'variance': (S2/n - (S1/n)**2) }


x1 = [1,-1,2,3,0,4.02,5]
x2 = [x+1e9 for x in x1]

print("naive_stats:")
print(naive_stats(x1))
print(naive_stats(x2))

print("stats:")
print(stats(x1))
print(stats(x2))


print("\n\nx3:")
random.seed(7)
x3 = random.rand(10000)
print(naive_stats(x3))
print(stats(x3))
m, s = statsnp(x3)
plt.plot(s, label='std')
plt.plot(m, label='avg')
plt.legend()
plt.show()