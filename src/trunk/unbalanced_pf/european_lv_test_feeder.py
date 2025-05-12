import pandas as pd
import GridCalEngine.api as gce
from GridCalEngine import WindingType

grid = gce.MultiCircuit()

def find_bus_by_name(grid, name):
    for bus in grid.buses:
        if bus.name == name:
            return bus
    return None

source = gce.Bus(name='Source', latitude=390872.8, longitude=392887.5, Vnom=11)
source.is_slack = True
gen = gce.Generator(vset = 1.05)
grid.add_generator(bus = source, api_obj = gen)

buses = pd.read_csv('European_LV_CSV/Buscoords.csv', skiprows=1)
buses.columns = ['Bus', 'X', 'Y']

for _, row in buses.iterrows():
    bus = gce.Bus(name=row['Bus'], latitude=row['X'], longitude=row['Y'], Vnom=0.416)
    grid.add_bus(obj=bus)

transformer = pd.read_csv('European_LV_CSV/Transformer.csv', skiprows=1)
transformer.columns = ['name', 'phases', 'bus_from', 'bus_to', 'HV', 'LV', 'rate', 'conn_HV', 'conn_LV', '%X', '%R']

for _, row in transformer.iterrows():

    transformer = gce.Transformer2W(name=row['name'],
                                    bus_from=find_bus_by_name(grid, row['bus_from']),
                                    bus_to= find_bus_by_name(grid, row['bus_to']),
                                    HV=float(row['HV']),
                                    LV=float(row['LV']),
                                    rate=float(row['rate']),
                                    r=float(row['%R'])/100,
                                    x=float(row['%X'])/100
                                    )
    if row['conn_HV'] == ' Delta':
        conn_f = WindingType.Delta
    else:
        conn_f = WindingType.GroundedStar

    if row['conn_LV'] == ' Delta':
        conn_t = WindingType.Delta
    else:
        conn_t = WindingType.GroundedStar

lines = pd.read_csv('European_LV_CSV/Lines.csv', skiprows=1)
lines.columns = ['names', 'bus_from', 'bus_to', 'phases', 'length[m]', 'units', 'line_code']
lines = lines.drop('units', axis=1)
print(lines.head())