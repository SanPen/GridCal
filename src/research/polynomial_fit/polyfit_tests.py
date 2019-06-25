import numpy as np
from datetime import datetime, timedelta
from matplotlib import pyplot as plt


def to_integer(dt_time):
    return 10000*dt_time.year + 100*dt_time.month + dt_time.day


x0 = [datetime(hour=3, year=2000, month=1, day=1),
      datetime(hour=10, year=2000, month=1, day=1),
      datetime(hour=15, year=2000, month=1, day=1),
      datetime(hour=20, year=2000, month=1, day=1)]

y0 = [4, 12, 8, 16]

xt = np.r_[x0[-1] - timedelta(days=1),
           x0,
           x0[0] + timedelta(days=1)]

x = np.array([i.timestamp() / 1e6 for i in xt])
y = np.r_[y0[-1], y0, y0[0]]


x_t = np.linspace(np.min(x), np.max(x), 24)
cheb = np.polynomial.chebyshev.chebfit(x, y, deg=5)
p = np.poly1d(cheb)
y_t = p(x_t)

fig = plt.figure(figsize=(12, 10), facecolor='w', edgecolor='k')
ax = fig.add_subplot(111)
ax.plot(x, y, 'o')
ax.plot(x_t, y_t)

plt.show()