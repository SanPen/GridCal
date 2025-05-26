import matplotlib.pyplot as plt

# Data from the table
buses = [5, 9, 14, 18, 30, 39, 57, 89]
contingencies = [6, 9, 20, 17, 41, 46, 80, 209]

# Create the plot
plt.figure(figsize=(8, 6))
plt.plot(buses, contingencies, marker='o', linestyle='-', linewidth=2)

# Add labels and title
plt.title('N-1 Contingencies vs. Grid Size')
plt.xlabel('Number of Buses')
plt.ylabel('Number of Contingencies (Deactivate Branches)')
plt.grid(True)

# Optionally annotate the points
for x, y in zip(buses, contingencies):
    plt.annotate(f'({x}, {y})', (x, y), textcoords="offset points", xytext=(5,5), ha='center')

# Show the plot
plt.tight_layout()
plt.show()

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# Data from the table
buses = np.array([5, 9, 14, 18, 30, 39, 57, 89])
contingencies = np.array([6, 9, 20, 17, 41, 46, 80, 209])

# Define the exponential model: B(N) = a * exp(b * N)
def exponential_model(N, a, b):
    return a * np.exp(b * N)

# Fit the model to the data
params, _ = curve_fit(exponential_model, buses, contingencies, p0=[10, 0.03])
a_fit, b_fit = params

# Generate values for the fitted curve
x_fit = np.linspace(min(buses), max(buses), 500)
y_fit = exponential_model(x_fit, a_fit, b_fit)

# Create the plot
plt.figure(figsize=(8, 6))
plt.plot(buses, contingencies, 'o')
plt.plot(x_fit, y_fit, '-', label=f'Best Fit: y(n) = {a_fit:.2f} ⋅ exp({b_fit:.4f}n)')

# Add labels and title
plt.title('N-1 Contingencies vs. Grid Size')
plt.xlabel('Number of Buses (n)')
plt.ylabel('Number of Contingencies (y)')
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()
