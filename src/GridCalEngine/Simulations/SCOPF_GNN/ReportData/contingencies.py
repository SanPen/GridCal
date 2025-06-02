import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# Extended dataset
buses = np.array([5, 9, 14, 25, 30, 39, 57, 89, 118, 145, 200, 300, 1354, 1888, 2000, 2868, 2869, 3012, 3125])
contingencies = np.array([6, 9, 20, 39, 41, 46, 80, 210, 186, 453, 245, 411, 1991, 2531, 3208, 3808, 4582, 3572, 3693])

# Define the linear model: y = m * x + c
def linear_model(x, m, c):
    return m * x + c

# Fit the linear model to the data
params, _ = curve_fit(linear_model, buses, contingencies)
m_fit, c_fit = params

# Generate values for the fitted line
x_fit = np.linspace(min(buses), max(buses), 500)
y_fit = linear_model(x_fit, m_fit, c_fit)

# Create the plot
plt.figure(figsize=(10, 7))
plt.plot(buses, contingencies, 'o')
plt.plot(x_fit, y_fit, '-', label=f'Best Fit Line: y = {m_fit:.2f}x + {c_fit:.2f}')

# Add labels and title
plt.title('N-1 Contingencies vs. Grid Size (Linear Fit)')
plt.xlabel('Number of Buses')
plt.ylabel('Number of Contingencies')
plt.grid(True)
plt.legend()

# Annotate the points
# for x, y in zip(buses, contingencies):
#     plt.annotate(f'({x}, {y})', (x, y), textcoords="offset points", xytext=(5,5), ha='center')

# plt.annotate(f'({39}, {46})', (39, 46), textcoords="offset points", xytext=(5,5), ha='center')
# plt.annotate(f'({89}, {210})', (39, 46), textcoords="offset points", xytext=(5,5), ha='center')
# plt.annotate(f'({14}, {30})', (39, 46), textcoords="offset points", xytext=(5,5), ha='center')

# Layout and show
plt.tight_layout()
plt.show()


# import matplotlib.pyplot as plt
#
# # Data from the table
# buses = [5, 9, 14, 18, 30, 39, 57, 89]
# contingencies = [6, 9, 20, 17, 41, 46, 80, 209]
#
# # Create the plot
# plt.figure(figsize=(8, 6))
# plt.plot(buses, contingencies, marker='o', linestyle='-', linewidth=2)
#
# # Add labels and title
# plt.title('N-1 Contingencies vs. Grid Size')
# plt.xlabel('Number of Buses')
# plt.ylabel('Number of Contingencies (Deactivate Branches)')
# plt.grid(True)
#
# # Optionally annotate the points
# for x, y in zip(buses, contingencies):
#     plt.annotate(f'({x}, {y})', (x, y), textcoords="offset points", xytext=(5,5), ha='center')
#
# # Show the plot
# plt.tight_layout()
# plt.show()
#
# import numpy as np
# import matplotlib.pyplot as plt
# from scipy.optimize import curve_fit
#
# # Data from the table
# buses = np.array([5, 9, 14, 18, 30, 39, 57, 89])
# contingencies = np.array([6, 9, 20, 17, 41, 46, 80, 209])
#
# # Define the exponential model: B(N) = a * exp(b * N)
# def exponential_model(N, a, b):
#     return a * np.exp(b * N)
#
# # Fit the model to the data
# params, _ = curve_fit(exponential_model, buses, contingencies, p0=[10, 0.03])
# a_fit, b_fit = params
#
# # Generate values for the fitted curve
# x_fit = np.linspace(min(buses), max(buses), 500)
# y_fit = exponential_model(x_fit, a_fit, b_fit)
#
# # Create the plot
# plt.figure(figsize=(8, 6))
# plt.plot(buses, contingencies, 'o')
# plt.plot(x_fit, y_fit, '-', label=f'Best Fit: y(n) = {a_fit:.2f} ⋅ exp({b_fit:.4f}n)')
#
# # Add labels and title
# plt.title('N-1 Contingencies vs. Grid Size')
# plt.xlabel('Number of Buses (n)')
# plt.ylabel('Number of Contingencies (y)')
# plt.grid(True)
# plt.legend()
# plt.tight_layout()
# plt.show()
