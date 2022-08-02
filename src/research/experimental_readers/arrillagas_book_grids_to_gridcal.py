import pandas as pd
import GridCal.Engine as gce

f_name = 'New Zealand shouth island (Arrillaga p150).xlsx'
f = pd.ExcelFile(f_name)
buses = pd.read_excel(f, sheet_name='Buses')
branches = pd.read_excel(f, sheet_name='Branches')
machines = pd.read_excel(f, sheet_name='Machines')

# grid
grid = gce.MultiCircuit()

# buses
bus_dict = dict()

for i, row in buses.iterrows():
    elm = gce.Bus()
    elm.name = row['Name']
    elm.Vnom = row['Vnom']

    # associated load
    if row['P'] != 0.0 and row['Q'] != 0.0:
        load = gce.Load(name=elm.name,
                        P=row['P'],
                        Q=row['Q'])
        elm.add_device(load)

    # register the device
    bus_dict[elm.name] = elm
    grid.add_bus(elm)

for i, row in branches.iterrows():
    elm = gce.Line(bus_from=bus_dict[row['FROM']],
                   bus_to=bus_dict[row['TO']],
                   r=row['R1'],
                   x=row['X1'],
                   b=row['B'],
                   r0=row['R0'],
                   x0=row['X0'],
                   r2=row['R2'],
                   x2=row['X2'])
    grid.add_line(elm)

for i, row in machines.iterrows():

    elm = gce.Generator(name=row['NAME'],
                        active_power=row['P'],
                        r1=row['R1'],
                        x1=row['X1'],
                        r0=row['R0'],
                        x0=row['X0'],
                        r2=row['R2'],
                        x2=row['X2'])
    bus = bus_dict[row['NAME']]
    bus.add_device(elm)

gce.FileSave(grid, f_name.replace(".xlsx", ".gridcal")).save()

print()
