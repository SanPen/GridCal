import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter, LogFormatter, LogLocator
import pandas as pd

df = pd.read_excel("All matpower grids.xlsx")

plt.yscale('log')
# Plot 4: Time vs Iterations (line plot)
plt.figure(figsize=(8, 6))
plt.scatter(df['n_buses'].values.astype(int),
            df['error (p.u.)'].values.astype(float),
            marker='o', color='#28a745', alpha=0.6, s=100)
plt.title('Number of buses vs Error')
plt.xlabel('Number of buses')
plt.ylabel('error (p.u.)', labelpad=10)
plt.xscale('log')
plt.yscale('log')
ax = plt.gca()
# ax.yaxis.set_major_locator(LogLocator(base=10.0, subs='auto', numticks=10))  # Set log scale with ticks
# ax.yaxis.set_major_formatter(LogFormatter(base=10.0))  # Format the ticks in log format
plt.grid(True)
plt.savefig('n_buses_vs_error.png')  # Save to disk
plt.show()

# Plot 4: Time vs Iterations (line plot)

plt.figure(figsize=(8, 6))
plt.scatter(df['n_buses'].values.astype(int),
            df['time (s)'].values.astype(float),
            marker='o', color='#4169E1', alpha=0.6, s=100)
plt.title('Number of buses vs time (s)')
plt.xlabel('Number of buses')
plt.ylabel('time (s)', labelpad=10)
plt.xscale('log')
plt.yscale('log')
# ax = plt.gca()
# ax.yaxis.set_major_locator(LogLocator(base=10.0, subs='auto', numticks=10))  # Set log scale with ticks
# ax.yaxis.set_major_formatter(LogFormatter(base=10.0))  # Format the ticks in log format
plt.grid(True)
plt.savefig('n_buses_vs_time.png')  # Save to disk
plt.show()