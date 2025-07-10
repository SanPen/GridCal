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

buses = pd.read_csv('European_LV_CSV/Buscoords.csv', skiprows=1)
buses.columns = ['Bus', 'X', 'Y']
bus_dict = dict()

i = 0
for _, row in buses.iterrows():
    bus = gce.Bus(name=str(row['Bus']), xpos=float(row['X']), ypos=float(row['Y']), Vnom=0.416)
    if i == 0:
        bus.is_slack = True
        gen = gce.Generator()
        grid.add_generator(bus=bus, api_obj=gen)
        i+=1
    grid.add_bus(obj=bus)
    bus_dict[int(float(bus.name))] = bus

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
loads_shape = pd.read_csv('European_LV_CSV/LoadShapes.csv', header=1)
load_phase_dict = dict()
shape_profile = {row['Name']:row['File'] for i,row in loads_shape.iterrows()}

profile_random = pd.read_csv('European_LV_CSV/Load Profiles/Load_profile_1.csv', parse_dates=['time'])
grid.set_time_profile(unix_data=np.arange(profile_random.shape[0]))

for _, row in loads.iterrows():
    load = gce.Load()
    bus = bus_dict[row['Bus']]

    profile_name = shape_profile[row['Yearly']]
    scale_df = pd.read_csv(f'European_LV_CSV/Load Profiles/{profile_name}')
    scale = scale_df['mult'].values

    if row['phases'] == 'A':
        load.Pa = float(row['kW']) / 1000
        load.Qa = Q_from_PF(0.95, load.Pa)
        load.Pa_prof = load.Pa * scale
        load.Qa_prof = load.Qa * scale
    elif row['phases'] == 'B':
        load.Pb = float(row['kW']) / 1000
        load.Qb = Q_from_PF(0.95, load.Pb)
        load.Pb_prof = load.Pb * scale
        load.Qb_prof = load.Qb * scale
    else:
        load.Pc = float(row['kW']) / 1000
        load.Qc = Q_from_PF(0.95, load.Pc)
        load.Pc_prof = load.Pc * scale
        load.Qc_prof = load.Qc * scale

    grid.add_load(bus=bus, api_obj=load)

gce.save_file(grid=grid, filename='IEEE Test Distribution.gridcal')