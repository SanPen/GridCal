# 🔥 Power flow




![](figures/settings-pf.png)

Solver
    The power flow solver to use.

    - Newton-Raphson in power:
    - Newton-Raphson in current:
    - Newton-Raphson-Iwamoto:
    - Levenberg-Marquardt:
    - Fast-Decoupled:
    - Holomorphic-Embedding:
    - Linear AC approximation:
    - DC approximation:

    All these solvers are covered in the theory section.

Retry with other methods is failed:
    This option tries other numerical solvers to try to find a power flow solution.
    This option is relevant because different numerical algorithms may be more suited to certain grid configurations.
    In general the Newton-Raphson implementation in GridCal includes back-tracing and other innovations that make it
    a very competitive method to consider by default.

Automatic precision
    The precision to use for the numerical solvers depends on the magnitude of the power injections.
    If we are dealing with hundreds of MW, the precision may be `1e-3`, but if we are dealing with Watts, the precision has
    to be greater. The automatic precision checks the loading for a suitable precision such that the results are fine.

Precision
    Exponent of the numerical precision. i.e. `4` corresponds to `1e-4` MW in p.u. of precision

Numerical method max. iterations
    Number of "inner" iterations of the numerical method before terminating.

Outer loop max. iterations
    Number of "outer loop" iterations to figure out the values of the set controls.

Reactive power control mode
    This is the mode of reactive power control for the generators that are set in PV mode.

    - No control: The reactive power limits are not enforced.
    - Direct: The classic pq-pv switching algorithm.
    - Iterative: An iterative algorithm that uses the power flow as objective function to
      find suitable reactive power limits.

Q steepness factor (iterative ctrl.)
    Steepness factor for the iterative reactive power control.

Transformer taps control mode

    - No control: The transformer voltage taps control is not enforced.
    - Direct:
    - Iterative:

Apply temperature correction
    When selected the branches apply the correction of the resistance due to the temperature.

Apply impedance tolerances
    ???

GridCal has the most power flow features in any open-source software.
The following table shows the features present in each solver:

|                                                                     | Newton Raphson  |Powell Dog-leg|Levenberg-Marquardt|Iwamoto|Fast-decoupled|Gauss-seidel|Holomorphic embedding|Linear without voltage modules|Linear with voltage modules|
|---------------------------------------------------------------------|---|---|---|---|---|---|---|---|---|
| Local voltage control using a Generator.                            |  ✅ | ✅  | ✅  |  ✅ | ✅  | ✅  |  ✅ | ✅ |  ✅ |
| Remote voltage control using a Generator.                           | ✅  |  ✅ |  ✅ |  ✅ |  ✅ |   |   |   |   |
| Generator reactive power limits.                                    | ✅  |  ✅ |  ✅ |  ✅ | ✅  |  ✅ |   |   |   |
| Local and remote voltage control using a transformer's tap changer. | ✅  |  ✅ |  ✅ |   |   |   |   |   |   |
| Local active power control using a transformer's tap changer.       |  ✅ | ✅  |  ✅ |   |   |   |   |   |   |
| Local reactive power control using a transformer's tap changer.     | ✅  | ✅  | ✅  |   |   |   |   |   |   |
| Local and remote AC and DC voltage control using a converter.       | ✅  | ✅  | ✅  |   |   |   |   |   |   |
| Local AC and DC active power control using converter.               |✅   | ✅  |  ✅ |   |   |   |   |   |   |
| Local AC reactive power control using a converter.                  | ✅  | ✅  |  ✅ |   |   |   |   |   |   |
| 3-phase unbalanced.                                                 | ✅  | ✅  |  ✅ |   |   |   |   |   |   |




## API

Using the simplified API:

```python
import os
import GridCalEngine as gce

folder = os.path.join('..', 'Grids_and_profiles', 'grids')
fname = os.path.join(folder, 'IEEE39_1W.gridcal')
main_circuit = gce.open_file(fname)

results = gce.power_flow(main_circuit)

print(main_circuit.name)
print('Converged:', results.converged, 'error:', results.error)
print(results.get_bus_df())
print(results.get_branch_df())
```

Using the more complex library objects:

```python
import os
import GridCalEngine as gce

folder = os.path.join('..', 'Grids_and_profiles', 'grids')
fname = os.path.join(folder, 'IEEE14_from_raw.gridcal')
main_circuit = gce.open_file(fname)

options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
power_flow = gce.PowerFlowDriver(main_circuit, options)
power_flow.run()

print(main_circuit.name)
print('Converged:', power_flow.results.converged, 'error:', power_flow.results.error)
print(power_flow.results.get_bus_df())
print(power_flow.results.get_branch_df())
```

Output:

```text
IEEE14_from_raw

Converged: True error: 5.98e-08

Bus resuts:
           Vm     Va      P      Q
BUS 1    1.06   0.00 232.39 -16.55
BUS 2    1.04  -4.98  18.30  30.86
BUS 3    1.01 -12.73 -94.20   6.08
BUS 4    1.02 -10.31 -47.80   3.90
BUS 5    1.02  -8.77  -7.60  -1.60
BUS 6    1.07 -14.22 -11.20   5.23
BUS 7    1.06 -13.36   0.00   0.00
BUS 8    1.09 -13.36   0.00  17.62
BUS 9    1.06 -14.94 -29.50 -16.60
BUS 10   1.05 -15.10  -9.00  -5.80
BUS 11   1.06 -14.79  -3.50  -1.80
BUS 12   1.06 -15.08  -6.10  -1.60
BUS 13   1.05 -15.16 -13.50  -5.80
BUS 14   1.04 -16.03 -14.90  -5.00

Branch results:
                Pf         Qf          Pt         Qt               loading    Ploss     Qloss
1_2_1   156.882887 -20.404291 -152.585286  27.676248 15688288652036.908203 4.297600  7.271957
1_5_1    75.510380   3.854989  -72.747507   2.229360  7551037982438.064453 2.762872  6.084349
2_3_1    73.237578   3.560203  -70.914309   1.602232  7323757808601.912109 2.323269  5.162436
2_4_1    56.131495  -1.550352  -54.454837   3.020689  5613149456668.273438 1.676658  1.470337
2_5_1    41.516214   1.170996  -40.612460  -2.099032  4151621353697.657715 0.903753 -0.928036
3_4_1   -23.285691   4.473114   23.659136  -4.835650 -2328569062725.765625 0.373445 -0.362537
4_5_1   -61.158231  15.823642   61.672651 -14.201004 -6115823108351.800781 0.514420  1.622637
6_11_1    7.353277   3.560471   -7.297904  -3.444512   735327693069.753418 0.055373  0.115959
6_12_1    7.786067   2.503414   -7.714258  -2.353959   778606687855.751465 0.071809  0.149455
6_13_1   17.747977   7.216574  -17.535891  -6.798912  1774797671583.112793 0.212085  0.417662
7_8_1    -0.000000 -17.162967    0.000000  17.623448             -0.001718 0.000000  0.460481
7_9_1    28.074179   5.778690  -28.074179  -4.976621  2807417855964.891602 0.000000  0.802069
9_10_1    5.227551   4.219139   -5.214676  -4.184938   522755058212.680359 0.012875  0.034201
9_14_1    9.426380   3.610007   -9.310226  -3.362932   942638030136.208130 0.116154  0.247075
10_11_1  -3.785324  -1.615061    3.797906   1.644513  -378532426869.186707 0.012581  0.029451
12_13_1   1.614258   0.753959   -1.607959  -0.748260   161425771970.211853 0.006298  0.005698
13_14_1   5.643852   1.747172   -5.589774  -1.637068   564385175482.526855 0.054078  0.110105
4_7_1    28.074176  -9.681066  -28.074176  11.384281  2807417645485.176270 0.000000  1.703214
4_9_1    16.079758  -0.427611  -16.079758   1.732322  1607975830176.256104 0.000000  1.304711
5_6_1    44.087319  12.470682  -44.087319  -8.049520  4408731875605.579102 0.000000  4.421161
```


## Benchmark


### Running Matpower grids

![GridCal](figures/n_buses_vs_time.png)

Matpower's excellent formulations and consistency has allowed this and other
projects to develop, relying on its sound math. That is why GridCal reads Matpower
cases out of the box, without you having to do anything special.
And of course, GridCal solves all Matpower 8 provided grids,
solving the continental USA case in about 1 second:

| name                    | n_buses | n_branches | P imbalance (%) | Flat start | converged | error (p.u.) | iterations | time (ms) |
|-------------------------|---------|------------|-----------------|------------|-----------|--------------|------------|-----------|
| case_SyntheticUSA.m     |   82000 |     104121 |           -0.12 |      FALSE |      TRUE |     2.03E-08 |         13 |   3181.41 |
| case_ACTIVSg70k.m       |   70000 |      88207 |            0.64 |      FALSE |      TRUE |     8.00E-07 |          4 |   1170.59 |
| case_ACTIVSg25k.m       |   25000 |      32230 |           -2.72 |       TRUE |      TRUE |     7.77E-10 |         13 |    993.16 |
| case13659pegase.m       |   13659 |      20467 |         2411.01 |       TRUE |      TRUE |     1.66E-07 |          8 |    284.45 |
| case_ACTIVSg10k.m       |   10000 |      12706 |           -7.61 |      FALSE |      TRUE |     3.81E-11 |          5 |    152.66 |
| case9241pegase.m        |    9241 |      16049 |          683.53 |       TRUE |      TRUE |     9.97E-11 |         11 |    319.74 |
| case8387pegase.m        |    8387 |      14561 |          -44.18 |       TRUE |      TRUE |     1.27E-11 |         15 |    362.14 |
| case6515rte.m           |    6515 |       9037 |          -47.51 |      FALSE |      TRUE |     9.36E-08 |          7 |    132.49 |
| case6495rte.m           |    6495 |       9019 |          -48.91 |      FALSE |      TRUE |     1.08E-07 |          6 |    111.79 |
| case6470rte.m           |    6470 |       9005 |          -47.97 |      FALSE |      TRUE |     7.89E-09 |          7 |    130.71 |
| case6468rte.m           |    6468 |       9000 |          -46.27 |      FALSE |      TRUE |     1.20E-09 |          7 |    145.08 |
| case3375wp.m            |    3374 |       4161 |          -73.29 |      FALSE |      TRUE |     2.26E-09 |          5 |     52.88 |
| case3120sp.m            |    3120 |       3693 |          -99.96 |       TRUE |      TRUE |     1.56E-08 |         12 |    142.90 |
| case3012wp.m            |    3012 |       3572 |          -98.93 |      FALSE |      TRUE |     2.85E-10 |          6 |     67.21 |
| case2869pegase.m        |    2869 |       4582 |          561.42 |       TRUE |      TRUE |     1.22E-11 |         10 |     78.79 |
| case2868rte.m           |    2868 |       3808 |          -46.03 |       TRUE |      TRUE |     5.05E-07 |         15 |    119.37 |
| case2848rte.m           |    2848 |       3776 |          -41.34 |       TRUE |      TRUE |     1.30E-11 |         18 |    153.64 |
| case2746wp.m            |    2746 |       3514 |          -95.83 |       TRUE |      TRUE |     9.13E-09 |          9 |     72.19 |
| case2746wop.m           |    2746 |       3514 |          -96.55 |       TRUE |      TRUE |     2.78E-07 |          9 |    128.23 |
| case2737sop.m           |    2737 |       3506 |          -94.20 |       TRUE |      TRUE |     3.01E-10 |         11 |     94.70 |
| case2736sp.m            |    2736 |       3504 |          -95.17 |       TRUE |      TRUE |     1.74E-09 |         10 |    114.32 |
| case2383wp.m            |    2383 |       2896 |          -97.43 |       TRUE |      TRUE |     5.17E-12 |         10 |     87.65 |
| case_ACTIVSg2000.m      |    2000 |       3206 |           10.84 |       TRUE |      TRUE |     6.16E-10 |         12 |    136.57 |
| case1951rte.m           |    1951 |       2596 |          -45.97 |      FALSE |      TRUE |     6.67E-07 |          4 |     31.74 |
| case1888rte.m           |    1888 |       2531 |          -47.08 |      FALSE |      TRUE |     1.56E-07 |          5 |     39.21 |
| case1354pegase.m        |    1354 |       1991 |          862.85 |       TRUE |      TRUE |     7.43E-09 |          8 |     56.87 |
| case_ACTIVSg500.m       |     500 |        597 |            2.78 |       TRUE |      TRUE |     4.17E-09 |          7 |     19.51 |
| case300.m               |     300 |        411 |          -38.64 |       TRUE |      TRUE |     1.54E-09 |          8 |      7.69 |
| case_ACTIVSg200.m       |     200 |        245 |            6.48 |       TRUE |      TRUE |     3.07E-10 |          5 |     11.00 |
| case145.m               |     145 |        453 |         -100.00 |       TRUE |      TRUE |     1.04E-09 |          8 |     14.71 |
| case141.m               |     141 |        140 |         -100.00 |       TRUE |      TRUE |     4.69E-09 |          2 |      1.15 |
| case136ma.m             |     136 |        156 |         -100.00 |       TRUE |      TRUE |     1.14E-08 |          2 |      1.11 |
| case118zh.m             |     118 |        132 |         -100.00 |       TRUE |      TRUE |     1.46E-08 |          2 |      1.35 |
| case118.m               |     118 |        186 |          -28.33 |       TRUE |      TRUE |     1.94E-07 |          7 |      3.05 |
| case94pi.m              |      94 |         93 |         -100.00 |       TRUE |      TRUE |     2.08E-11 |          2 |      1.32 |
| case89pegase.m          |      89 |        210 |            4.19 |       TRUE |      TRUE |     2.81E-09 |          4 |      2.54 |
| case85.m                |      85 |         84 |         -100.00 |       TRUE |      TRUE |     7.90E-12 |          2 |      1.13 |
| case74ds.m              |      74 |         73 |         -100.00 |       TRUE |      TRUE |     8.74E-07 |          1 |      0.58 |
| case_RTS_GMLC.m         |      73 |        120 |          -80.55 |       TRUE |      TRUE |     1.62E-07 |          7 |     11.74 |
| case70da.m              |      70 |         76 |         -100.00 |       TRUE |      TRUE |     2.17E-12 |          2 |      0.89 |
| case69.m                |      69 |         68 |         -100.00 |       TRUE |      TRUE |     7.20E-09 |          2 |      0.78 |
| case60nordic.m          |      60 |         88 |           96.26 |       TRUE |      TRUE |     5.15E-08 |          4 |      1.35 |
| case57.m                |      57 |         80 |         -100.00 |       TRUE |      TRUE |     2.82E-10 |          7 |     11.47 |
| case51ga.m              |      51 |         50 |         -100.00 |       TRUE |      TRUE |     1.85E-12 |          2 |      0.86 |
| case51he.m              |      51 |         50 |         -100.00 |       TRUE |      TRUE |     6.16E-07 |          1 |      0.40 |
| case39.m                |      39 |         46 |          -26.13 |       TRUE |      TRUE |     1.93E-11 |          7 |     10.79 |
| case38si.m              |      38 |         37 |         -100.00 |       TRUE |      TRUE |     7.26E-12 |          2 |      1.06 |
| case34sa.m              |      34 |         33 |         -100.00 |       TRUE |      TRUE |     8.24E-13 |          2 |      0.74 |
| case33bw.m              |      33 |         37 |         -100.00 |       TRUE |      TRUE |     7.38E-09 |          2 |      1.09 |
| case33mg.m              |      33 |         37 |         -100.00 |       TRUE |      TRUE |     7.46E-12 |          2 |      0.70 |
| case30.m                |      30 |         41 |          -39.59 |       TRUE |      TRUE |     9.57E-10 |          3 |      1.13 |
| case_ieee30.m           |      30 |         41 |           -3.24 |       TRUE |      TRUE |     5.18E-08 |          3 |      0.92 |
| case30pwl.m             |      30 |         41 |          -39.59 |       TRUE |      TRUE |     9.57E-10 |          3 |      0.89 |
| case30Q.m               |      30 |         41 |          -39.59 |       TRUE |      TRUE |     9.57E-10 |          3 |      0.92 |
| case28da.m              |      28 |         27 |         -100.00 |       TRUE |      TRUE |     6.85E-07 |          1 |      0.53 |
| case24_ieee_rts.m       |      24 |         38 |          -70.52 |       TRUE |      TRUE |     1.63E-08 |          5 |      9.04 |
| case22.m                |      22 |         21 |         -100.00 |       TRUE |      TRUE |     2.13E-07 |          1 |      0.47 |
| case18.m                |      18 |         17 |         -100.00 |       TRUE |      TRUE |     1.27E-08 |          3 |      0.74 |
| case18nbr.m             |      18 |         17 |         -100.00 |       TRUE |      TRUE |     1.35E-07 |          2 |      0.84 |
| case17me.m              |      17 |         16 |         -100.00 |       TRUE |      TRUE |     3.19E-08 |          3 |      0.91 |
| case16ci.m              |      16 |         16 |         -100.00 |       TRUE |      TRUE |     1.38E-09 |          2 |      0.47 |
| case15da.m              |      15 |         14 |         -100.00 |       TRUE |      TRUE |     8.57E-07 |          1 |      0.68 |
| case15nbr.m             |      15 |         14 |         -100.00 |       TRUE |      TRUE |     5.43E-08 |          2 |      0.63 |
| case16am.m              |      15 |         14 |         -100.00 |       TRUE |      TRUE |     1.22E-07 |          2 |      0.89 |
| case14.m                |      14 |         20 |            1.26 |       TRUE |      TRUE |     5.98E-08 |          3 |      0.61 |
| case12da.m              |      12 |         11 |         -100.00 |       TRUE |      TRUE |     2.71E-07 |          1 |      1.36 |
| case10ba.m              |      10 |          9 |         -100.00 |       TRUE |      TRUE |     6.22E-08 |          2 |      0.52 |
| case9target.m           |       9 |          9 |          -41.08 |       TRUE |      TRUE |     1.40E-07 |          5 |      2.12 |
| case9_gurobi_test.m     |       9 |          9 |            1.68 |       TRUE |      TRUE |     3.42E-07 |          3 |      1.61 |
| case9.m                 |       9 |          9 |            1.68 |       TRUE |      TRUE |     3.42E-07 |          3 |      0.67 |
| case9Q.m                |       9 |          9 |          -21.27 |       TRUE |      TRUE |     5.71E-07 |          3 |      0.64 |
| case6ww.m               |       6 |         11 |          -47.62 |       TRUE |      TRUE |     2.09E-10 |          3 |      1.43 |
| case5.m                 |       5 |          6 |          -36.35 |       TRUE |      TRUE |     6.42E-11 |          3 |      1.87 |
| case4_dist.m            |       4 |          3 |         -100.00 |       TRUE |      TRUE |     4.63E-11 |          6 |      8.03 |
| case4gs.m               |       4 |          4 |         -100.00 |       TRUE |      TRUE |     6.59E-14 |          6 |      1.14 |
| contab_ACTIVSg200.m     |       0 |          0 |            0.00 |       TRUE |      TRUE |     0.00E+00 |          0 |      0.00 |
| contab_ACTIVSg500.m     |       0 |          0 |            0.00 |       TRUE |      TRUE |     0.00E+00 |          0 |      0.00 |
| scenarios_ACTIVSg200.m  |       0 |          0 |            0.00 |       TRUE |      TRUE |     0.00E+00 |          0 |      0.00 |
| contab_ACTIVSg10k.m     |       0 |          0 |            0.00 |       TRUE |      TRUE |     0.00E+00 |          0 |      0.00 |
| contab_ACTIVSg2000.m    |       0 |          0 |            0.00 |       TRUE |      TRUE |     0.00E+00 |          0 |      0.00 |
| scenarios_ACTIVSg2000.m |       0 |          0 |            0.00 |       TRUE |      TRUE |     0.00E+00 |          0 |      0.00 |

_Results simulated with AMD 9750x and 64 GB of RAM under Ubuntu 24.04.
All solved using Newton-Raphson, and only using the provided solution
that comes with the files when the flat start fails.

Cool right? This is the code to reproduce the results:

```python
import os
import pandas as pd
import multiprocessing as mp
import GridCalEngine as gce

folder = "[some path...]/matpower8.0b1/data"


def run_grid(fname):
    grid = gce.open_file(fname)
    name = os.path.basename(fname)

    if grid.get_bus_number() > 0:

        res = gce.power_flow(
            grid=grid,
            options=gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                         retry_with_other_methods=False,
                                         use_stored_guess=False)
        )
        flat_start = True

        if not res.converged:
            # if it does not converge, retry with the provided solution
            res = gce.power_flow(
                grid=grid,
                options=gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                             retry_with_other_methods=False,
                                             use_stored_guess=True)
            )
            flat_start = False

        info = {
            "name": name,
            "n_buses": grid.get_bus_number(),
            "n_branches": grid.get_branch_number(),
            "P imbalance (%)": grid.get_imbalance() * 100.0,
            "Flat start": flat_start,
            "converged": res.converged,
            "error (p.u.)": res.error,
            "iterations": res.iterations,
            "time (ms)": res.elapsed * 1000.0,
        }


    else:
        info = {
            "name": name,
            "n_buses": grid.get_bus_number(),
            "n_branches": grid.get_branch_number(),
            "P imbalance (%)": 0.0,
            "Flat start": True,
            "converged": True,
            "error (p.u.)": 0,
            "iterations": 0,
            "time (ms)": 0,
        }

    return info


# run this one to compile all JIT routines and have fair measurements
gce.power_flow(gce.open_file(os.path.join(folder, "case_ieee30.m")))

data = list()
files_list = list()
for root, dirs, files in os.walk(folder):
    for file in files:
        if file.endswith(".m"):
            path = os.path.join(root, file)
            files_list.append(path)


with mp.Pool(mp.cpu_count()) as p:
    data = p.map(run_grid, files_list)

df = pd.DataFrame(data).sort_values(by='n_buses', ascending=False)
df.to_excel("All matpower grids.xlsx", index=False)
```
