import numpy as np
import pandas as pd

df = pd.read_excel('Solutions/GridLAB-D/Snapshots/Snapshot_1min_Initialization_Off Peak.xlsx',header=1)
#df = pd.read_excel('Solutions/GridLAB-D/Snapshots/Snapshot_566min_On Peak.xlsx',header=1)
print(df.head())

# Define scaling factor
scaling_factor = 416 / np.sqrt(3)

# Scale voltage magnitudes
for col in ['voltA_mag', 'voltB_mag', 'voltC_mag']:
    df[col] = df[col] / scaling_factor

# Convert angles to degrees
for col in ['voltA_angle', 'voltB_angle', 'voltC_angle']:
    df[col] = np.degrees(df[col])

# Save updated DataFrame to new Excel file
df.to_excel("compare_to.xlsx", index=False)