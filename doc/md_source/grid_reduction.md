# Grid Reduction

GridCal has the ability to perform planning-style grid reductions.

A) From the schematic:

1. First, Select the buses that you want to reduce in the schematic.

2. The launch the grid reduction window by selecting the menu option `Model > Grid Reduction`

B) From the database:

1. Select the buses according to some rule in the database view. 
2. Right click and call the **grid reduction** action in the context menu.

![](figures/grid_reduction_1.png)


A small window  will pop up indicating the list of buses that you are going to remove.
By accepting, the grid will be reduced according to the theory developed by [1].
You can expect that the reduced grid flows behave roughly like the original grid.

Changing the injections, or further topological changes will alter the equivalent behavior.

This action cannot be undone.

## Theory

The PhD dissertation presented in [1], expands on the traditional ward equivalent reduction method.
The proposed method allows the generators to be "just moved" to the boundary buses and later, 
injections are calibrated to compensate for that. In that sense, is a very friendly method for 
planning engineers that want to reduce the grid, and still need to keep the generators as previously 
defined for dispatching.

Steps for the **Modified Ward equivalent**:


**Step 1 – First Ward reduction**

1. Inputs:

   - Full original system network.

    - A list of retained buses (the boundary buses you want to keep).

2. Preparation:

   - Convert all equivalent shunt elements into PQ loads.

   - This makes the load representation compatible with the Ward reduction.

3. Apply Ward reduction:

   - Eliminate all non-retained (external) buses.

   - Replace their effects with equivalent injections and lines.

4. Post-processing:

   - Since the original system has many very low-impedance lines (<0.01 p.u.), some artificial lines created by reduction can be unrealistically large.

   - Therefore, remove any equivalent line with impedance > 5 p.u. from the reduced system.

**Step 2 – Reduced generator model**

5. Update the set of retained buses:

   - Keep all generator buses.

   - Keep all the retained boundary buses from Step 1.

6. Apply Ward reduction again:

   - This produces the reduced generator model.

   - In this model, every generator bus is guaranteed to connect to at least one retained (boundary) bus by a transmission line (either original or equivalent).

7. Generator relocation (different from classical Ward):

   - Classical Ward would “fractionalize” generators (split them into pieces assigned to multiple boundary buses).

   - Instead, the proposed method keeps each generator intact:

     - For each generator bus, find the closest retained bus.

     - Closest = electrically closest, meaning the path with the smallest equivalent impedance between the generator bus and the retained bus.

   - Move the entire generator to that closest internal (retained) bus.

The pseudo-code would be like:

```python 
# Step 1: Initial Ward reduction
convert_shunts_to_PQ()
reduced_system = ward_reduction(original_system, retained_buses)
remove_lines_if_impedance_gt(reduced_system, threshold=5.0)

# Step 2: Reduced generator model
new_retained_buses = retained_buses + generator_buses
reduced_generator_model = ward_reduction(original_system, new_retained_buses)

# Step 3: Generator relocation
for gen in reduced_generator_model.generators:
    closest_bus = find_min_impedance_path(gen.bus, retained_buses)
    move_generator(gen, closest_bus)
```

[1]: [Power System Network Reduction for Engineering and Economic 
Analysis by Di Shi, 
2012 Arizona State University](https://core.ac.uk/download/pdf/79564835.pdf).