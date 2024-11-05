import GridCalEngine.api as gce

grid = gce.MultiCircuit()

line_name = "172845235_WCR_OVERHEAD_ACSR_150MM2_33 KV"
terminal_i_coords = {'lat': 13.4527, 'lon': -16.5780}  # Bus1
terminal_j_coords = {'lat': 13.4530, 'lon': -16.5785}  # Bus2

bus1 = gce.Bus("Bus1", latitude=terminal_i_coords['lat'], longitude=terminal_i_coords['lon'])
bus1.Vnom = 110
bus1.Vmax = 115
bus1.Vmin = 105
grid.add_bus(bus1)

bus2 = gce.Bus("Bus2", latitude=terminal_j_coords['lat'], longitude=terminal_j_coords['lon'])
bus2.Vnom = 110
bus2.Vmax = 115
bus2.Vmin = 105
grid.add_bus(bus2)

branch = gce.Branch(bus1, bus2, name=line_name, r=0.05, x=0.11, b=0.02)  # Örnek direnç ve reaktans değerleri
grid.add_branch(branch)

grid.fill_xy_from_lat_lon(destructive=True)
gce.detect_substations(grid)

gce.save_file(grid, "example_yns0671.gridcal")
