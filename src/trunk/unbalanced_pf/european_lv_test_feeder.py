import pandas as pd
import numpy as np
import GridCalEngine.api as gce
from GridCalEngine import WindingType

logger = gce.Logger()

grid = gce.MultiCircuit()

def Q_from_PF(pf, p):
    pf2 = np.power(pf, 2.0)
    pf_sign = (pf + 1e-20) / np.abs(pf + 1e-20)
    Q = pf_sign * p * np.sqrt((1.0 - pf2) / (pf2 + 1e-20))
    return Q

source = gce.Bus(name='SourceBus', xpos=390872.8, ypos=392887.5, Vnom=11)
source.is_slack = True
grid.add_bus(obj=source)
gen = gce.Generator(vset = 1.05)
grid.add_generator(bus = source, api_obj = gen)

buses = pd.read_csv('European_LV_CSV/Buscoords.csv', skiprows=1)
buses.columns = ['Bus', 'X', 'Y']
bus_dict = dict()
bus_dict[source.name] = source

for _, row in buses.iterrows():
    bus = gce.Bus(name=str(row['Bus']), xpos=float(row['X']), ypos=float(row['Y']), Vnom=0.416)
    grid.add_bus(obj=bus)
    bus_dict[int(float(bus.name))] = bus

transformer = pd.read_csv('European_LV_CSV/Transformer.csv', skiprows=1)
transformer.columns = ['name', 'phases', 'bus_from', 'bus_to', 'HV', 'LV', 'rate', 'conn_HV', 'conn_LV', '%X', '%R']

for _, row in transformer.iterrows():

    transformer = gce.Transformer2W(name=row['name'],
                                    bus_from=source,
                                    bus_to= bus_dict[row['bus_to']],
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

    grid.add_transformer2w(transformer)

lines = pd.read_csv('European_LV_CSV/Lines.csv', header=1)
lines.columns = ['names', 'bus_from', 'bus_to', 'phases', 'length[m]', 'units', 'line_code']
lines = lines.drop(['units', 'names', 'phases'], axis=1)
lines_codes = pd.read_csv('European_LV_CSV/LineCodes.csv', header=1)
line_types_dict = dict()

for _, row in lines_codes.iterrows():

    line_type = gce.SequenceLineType(R=row['R1'],
                                      X=row['X1'],
                                      R0=row['R0'],
                                      X0=row['X0'],
                                      CnF=row['C1'],
                                      CnF0=row['C0'],
                                      name=row['Name']
                                      )
    line_types_dict[line_type.name] = line_type
    grid.add_sequence_line(line_type)

for _, row in lines.iterrows():

    line = gce.Line(bus_from=bus_dict[row['bus_from']],
                    bus_to=bus_dict[row['bus_to']],
                    length=float(row['length[m]'])/1000,
                    )
    template = line_types_dict[row['line_code']]
    line.apply_template(template, grid.Sbase, grid.fBase, logger)
    grid.add_line(obj=line)

loads = pd.read_csv('European_LV_CSV/Loads.csv', header=2)
load_phase_dict = dict()

for _, row in loads.iterrows():
    load = gce.Load()
    bus = bus_dict[row['Bus']]

    if row['phases'] == 'A':
        load.P1 = float(row['kW']) / 1000 /100
        load.Q1 = Q_from_PF(0.95, load.P1)
    elif row['phases'] == 'B':
        load.P2 = float(row['kW']) / 1000 /100
        load.Q2 = Q_from_PF(0.95, load.P2)
    else:
        load.P3 = float(row['kW']) / 1000 /100
        load.Q3 = Q_from_PF(0.95, load.P3)

    grid.add_load(bus=bus, api_obj=load)

gce.save_file(grid=grid, filename='IEEE Test Distribution.gridcal')