import numpy as np
import matplotlib.pyplot as plt
import pandas as pd


df_random = pd.read_excel('random_trial.xlsx')
df_nsga = pd.read_excel('nsga.xlsx')

plt.plot(df_random[0], df_random[4], 'ro', label='Random')
plt.plot(df_nsga[0], df_nsga[4], 'bo', label='NSGA3')
plt.show()


# Plot Pareto front with all saved data
# Files can be read from Excel (xlsx) or csv
data_rand = pd.read_excel("random_trial.xlsx")
data_nsga = pd.read_csv("nsga3.csv")

investment_cost_rand = data_rand.iloc[:, 5]
technical_cost_rand = data_rand.iloc[:, 1] * 10 ** 5

investment_cost_nsga = data_nsga["Investment cost (M€)"]
technical_cost_nsga = data_nsga["Technical cost (M€)"] * 10 ** 5

combined_cost_nsga = investment_cost_nsga + technical_cost_nsga
combined_cost_rand = investment_cost_rand + technical_cost_rand

plt.scatter(investment_cost_nsga, technical_cost_nsga, c=combined_cost_nsga, cmap='YlOrRd', label='NSGA3', s=10,
            alpha=0.8)
plt.colorbar(label='Objective function (NSGA3)')
plt.scatter(investment_cost_rand, technical_cost_rand, c=combined_cost_rand, cmap='viridis', label="Random", s=10, alpha=0.8)
plt.colorbar(label='Objective function (Random)')

plt.xlabel("Coste técnico (M€)")
plt.ylabel("Coste económico (M€)")
plt.title("Pareto Front")
plt.legend(["Random", "NSGA3"])
plt.legend()
plt.show()