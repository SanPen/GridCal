# ⚡ Short circuit


GridCal has unbalanced short circuit calculations. Now let's run a line-ground short circuit in the third bus of
the South island of New Zealand grid example from reference book
_Computer Analysis of Power Systems by J. Arrillaga and C.P. Arnold_

```python
import os
import GridCalEngine as gce

folder = os.path.join('..', 'Grids_and_profiles', 'grids')
fname = os.path.join(folder, 'South Island of New Zealand.gridcal')

grid = gce.open_file(filename=fname)

# Define fault index explicitly
fault_index = 2

# Run a Line-Ground short circuit on the bus at index 2
# Since we do not provide any power flow results, it will run one for us
results = gce.short_circuit(grid, fault_index, fault_type=gce.FaultType.LG)

print("Short circuit power: ", results.SCpower[fault_index])
```

A more elaborated way to run the simulation, controlling all the steps:

```python
import os
import GridCalEngine as gce

folder = os.path.join('..', 'Grids_and_profiles', 'grids')
fname = os.path.join(folder, 'South Island of New Zealand.gridcal')

grid = gce.open_file(filename=fname)

pf_options = gce.PowerFlowOptions()
pf = gce.PowerFlowDriver(grid, pf_options)
pf.run()

fault_index = 2
sc_options = gce.ShortCircuitOptions(bus_index=fault_index,
                                     fault_type=gce.FaultType.LG)

sc = gce.ShortCircuitDriver(grid, options=sc_options,
                            pf_options=pf_options,
                            pf_results=pf.results)
sc.run()

print("Short circuit power: ", sc.results.SCpower[fault_index])
```

Output:

```text
Short circuit power:  -217.00 MW - 680.35j MVAr
```

Sequence voltage, currents and powers are also available.