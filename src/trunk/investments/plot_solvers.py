import numpy as np
import matplotlib.pyplot as plt
import pandas as pd


df_random = pd.read_excel('random_trial.xlsx')
df_nsga = pd.read_excel('nsga.xlsx')

plt.plot(df_random[0], df_random[4], 'ro', label='Random')
plt.plot(df_nsga[0], df_nsga[4], 'bo', label='NSGA3')
plt.show()