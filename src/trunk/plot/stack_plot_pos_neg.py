import numpy as np
import matplotlib.pyplot as plt

# Example: Create sample time and data arrays
# Let's assume 100 time points
t = np.linspace(0, 10, 100)

# Create an example 2D array with 3 series. For demonstration,
# one series will naturally have both positive and negative values.
data = np.array([
    np.sin(t),         # Series 1: Sine wave, varying between -1 and 1
    np.cos(t),         # Series 2: Cosine wave, also between -1 and 1
    0.5 * np.sin(2*t)  # Series 3: Smaller amplitude sine wave
]).T  # Transpose so that shape is (time, series)

# For demonstration, force one series to be mostly negative by scaling it.
data[:, 1] *= -1  # Multiply the second series by -1

# ----------------------------------------------------------------------------
# Step 1: Split the data into positive and negative parts
# ----------------------------------------------------------------------------
data_pos = np.where(data > 0, data, 0)
data_neg = np.where(data < 0, data, 0)

# ----------------------------------------------------------------------------
# Step 2: Compute the cumulative sums along the series axis (axis=1)
# ----------------------------------------------------------------------------
cum_pos = np.cumsum(data_pos, axis=1)
cum_neg = np.cumsum(data_neg, axis=1)

# ----------------------------------------------------------------------------
# Step 3: Plot the stacks using fill_between
# ----------------------------------------------------------------------------
fig, ax = plt.subplots()

# Define colors for each series (using a colormap for variety)
colors = plt.cm.viridis(np.linspace(0, 1, data.shape[1]))

# Plot the positive values stack:
for i in range(data.shape[1]):
    if i == 0:
        # For the first series, fill from baseline 0 to its cumulative sum
        ax.fill_between(t, 0, cum_pos[:, i], color=colors[i], label=f'Series {i+1} (pos)')
    else:
        # For subsequent series, fill between the previous cumulative sum and the new one
        ax.fill_between(t, cum_pos[:, i-1], cum_pos[:, i], color=colors[i], label=f'Series {i+1} (pos)')

# Plot the negative values stack:
for i in range(data.shape[1]):
    if i == 0:
        # For the first series, fill from baseline 0 down to its cumulative negative sum
        ax.fill_between(t, 0, cum_neg[:, i], color=colors[i], alpha=0.6, label=f'Series {i+1} (neg)')
    else:
        ax.fill_between(t, cum_neg[:, i-1], cum_neg[:, i], color=colors[i], alpha=0.6, label=f'Series {i+1} (neg)')

# Add legend and labels for clarity
ax.set_title('Stack Plot with Positive and Negative Values')
ax.set_xlabel('Time')
ax.set_ylabel('Value')
ax.legend(loc='upper right', fontsize='small')

plt.show()
