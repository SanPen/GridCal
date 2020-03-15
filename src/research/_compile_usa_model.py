import os
import pandas as pd
from GridCal.Engine import *


folder = '/home/santi/Descargas/USATestSystem/SyntheticUSA_IV'

branch_df = pd.read_csv(os.path.join(folder, 'branch.csv'))
bus_df = pd.read_csv(os.path.join(folder, 'bus.csv'))
bus2sub_df = pd.read_csv(os.path.join(folder, 'bus2sub.csv'))
dcline_df = pd.read_csv(os.path.join(folder, 'dcline.csv'))
demand_df = pd.read_csv(os.path.join(folder, 'demand.csv'))
gencost_df = pd.read_csv(os.path.join(folder, 'gencost.csv'))
hydro_df = pd.read_csv(os.path.join(folder, 'hydro.csv'))
plant_df = pd.read_csv(os.path.join(folder, 'plant.csv'))
solar_df = pd.read_csv(os.path.join(folder, 'solar.csv'))
sub_df = pd.read_csv(os.path.join(folder, 'sub.csv'))
wind_df = pd.read_csv(os.path.join(folder, 'wind.csv'))
zone_df = pd.read_csv(os.path.join(folder, 'zone.csv'))

bus_df2 = pd.merge(pd.merge(pd.merge(bus_df,
                            bus2sub_df, on='bus_id'),
                            sub_df, on='sub_id'),
                            zone_df, on='zone_id')
grid = MultiCircuit('USA')
bus_dict = dict()
for i, entry in bus_df2.iterrows():

    bus = Bus(name=str(entry['bus_id']),
              vnom=entry['baseKV'],
              vmin=entry['Vmin'],
              vmax=entry['Vmax'],
              r_fault=0.0,
              x_fault=0.0,
              xpos=0,
              ypos=0,
              height=40,
              width=80,
              active=True,
              is_slack=False,
              area='Default',
              zone=entry['zone_name'],
              substation=entry['name'],
              country='USA',
              longitude=entry['lon'],
              latitude=entry['lat'])

    if (entry['Bs'] + entry['Gs']) != 0.0:
        sh = Shunt(name='Sh' + str(i), G=entry['Gs'], B=entry['Bs'])
        bus.add_device(sh)

    if (entry['Pd'] + entry['Pd']) != 0.0:
        ld = Load(name='Load' + str(i), P=entry['Pd'], Q=entry['Qd'], cost=1200.0)
        bus.add_device(ld)

    bus_dict[entry['bus_id']] = bus

    grid.add_bus(bus)

br_types = {'Line': BranchType.Line,
            'Transformer': BranchType.Transformer,
            'TransformerWinding': BranchType.Transformer}

for i, entry in branch_df.iterrows():
    id = str(entry['branch_id'])
    f = bus_dict[entry['from_bus_id']]
    t = bus_dict[entry['to_bus_id']]
    tpe = br_types[entry['branch_device_type']]
    tap = entry['ratio']
    if tap == 0.0:
        tap = 1.0

    branch = Branch(bus_from=f,
                    bus_to=t,
                    name=id,
                    r=entry['r'],
                    x=entry['x'],
                    b=entry['b'],
                    rate=entry['rateA'],
                    tap=tap,
                    shift_angle=0,
                    active=bool(entry['status']),
                    tolerance=0,
                    cost=1000.0,
                    branch_type=tpe)

    grid.add_branch(branch)

FileSave(grid, 'USA.gridcal').save()