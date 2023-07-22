import pandas as pd
import pvlib

# Define location coordinates
latitude = 37.7749
longitude = -122.4194
altitude = 10  # meters above sea level

# Define PV system parameters
system_capacity = 5  # kW
module_parameters = {
    'pdc0': 200,  # DC power at STC
    'gamma_pdc': -0.004  # Temperature coefficient of PDC
}
inverter_parameters = {
    'pdc0': 5  # DC input power required to produce 1 unit of AC output power
}

# Specify time range and frequency for the simulation
start_date = pd.Timestamp('2023-01-01', tz='America/Los_Angeles')
end_date = pd.Timestamp('2023-01-07', tz='America/Los_Angeles')
frequency = '1h'  # Hourly data

# Retrieve weather data using NSRDB
weather_data, metadata = pvlib.iotools.get_psm3(latitude=latitude,
                                                longitude=longitude,
                                                names='2020',
                                                email='santiago.penate.vera@gmail.com',
                                                interval=60,
                                                api_key='3W0TPPEjU3ojyD3y8egsKPlpADJV4x295frW7HEC',
                                                leap_day=True)

# Create a PV system model
pv_system = pvlib.pvsystem.PVSystem(module_parameters=module_parameters, inverter_parameters=inverter_parameters)

# Run the simulation and calculate power output
power_output = pv_system.pvwatts_dc(weather=weather_data['GHI'], temp_air=weather_data['Temperature']) * system_capacity

# Print the power output data
print(power_output)

# Calculate total energy output
total_energy = power_output.sum() / 1000  # Convert Wh to kWh

# Print the total energy output
print(f"Total Energy Output: {total_energy:.2f} kWh")
