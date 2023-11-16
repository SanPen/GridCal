# Import Meteostat library and dependencies
from datetime import datetime
import matplotlib.pyplot as plt
from meteostat import Point, Daily, Hourly
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

# Set time period
start = datetime(2022, 1, 1)
end = datetime(2022, 12, 31)

# Create Point for Vancouver, BC
vancouver = Point(49.2497, -123.1193, 70)

# Get daily data for 2018
data = Hourly(vancouver, start, end)
#
df = data.fetch()
df.fillna(0, inplace=True)
# Plot line chart including average, minimum and maximum temperature
df.plot(y=['tavg', 'tmin', 'tmax'])
# df.plot(x=['wdir'], y=['wspd'], kind='polar')
plt.show()