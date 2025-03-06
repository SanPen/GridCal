import GridCalEngine.api as gce
import numpy as np

np.set_printoptions(linewidth=20000, precision=3, suppress=True)


def seq2abc(z0, z1):
    """
    Function to convert zero and positive impedances into ABC matrix of impedances
    """
    a = 2 * z1 + z0
    b = z0 - z1
    return np.array([
        [a, b, b],
        [b, a, b],
        [b, b, a],
    ])


# declare a circuit object
grid = gce.MultiCircuit()

# Add the buses and the generators and loads attached
bus1 = gce.Bus('Bus 1', Vnom=20)
# bus1.is_slack = True  # we may mark the bus a slack
grid.add_bus(bus1)

# add a generator to the bus 1
gen1 = gce.Generator('Slack Generator', vset=1.0)
grid.add_generator(bus1, gen1)

# add bus 2 with a load attached
bus2 = gce.Bus('Bus 2', Vnom=20)
grid.add_bus(bus2)
grid.add_load(bus2, gce.Load('load 2', P=40, Q=20))

# add bus 3 with a load attached
bus3 = gce.Bus('Bus 3', Vnom=20)
grid.add_bus(bus3)
grid.add_load(bus3, gce.Load('load 3', P=25, Q=15))

# add bus 4 with a load attached
bus4 = gce.Bus('Bus 4', Vnom=20)
grid.add_bus(bus4)
grid.add_load(bus4, gce.Load('load 4', P=40, Q=20))

# add bus 5 with a load attached
bus5 = gce.Bus('Bus 5', Vnom=20)
grid.add_bus(bus5)
grid.add_load(bus5, gce.Load('load 5', P=50, Q=20))

# add Lines connecting the buses
grid.add_line(gce.Line(bus1, bus2, name='line 1-2', r=0.05, x=0.11, b=0.02, r0=0.05 * 2, x0=0.11 * 2, b0=0.02 * 2))
grid.add_line(gce.Line(bus1, bus3, name='line 1-3', r=0.05, x=0.11, b=0.02, r0=0.05 * 2, x0=0.11 * 2, b0=0.02 * 2))
grid.add_line(gce.Line(bus1, bus5, name='line 1-5', r=0.03, x=0.08, b=0.02, r0=0.03 * 2, x0=0.08 * 2, b0=0.02 * 2))
grid.add_line(gce.Line(bus2, bus3, name='line 2-3', r=0.04, x=0.09, b=0.02, r0=0.04 * 2, x0=0.09 * 2, b0=0.02 * 2))
grid.add_line(gce.Line(bus2, bus5, name='line 2-5', r=0.04, x=0.09, b=0.02, r0=0.04 * 2, x0=0.09 * 2, b0=0.02 * 2))
grid.add_line(gce.Line(bus3, bus4, name='line 3-4', r=0.06, x=0.13, b=0.03, r0=0.06 * 2, x0=0.13 * 2, b0=0.03 * 2))
grid.add_line(gce.Line(bus4, bus5, name='line 4-5', r=0.04, x=0.09, b=0.02, r0=0.04 * 2, x0=0.09 * 2, b0=0.02 * 2))

Zbase = (bus4.Vnom ** 2) / grid.Sbase
Zs_per_km = np.array([[0.5706 + 0.4848j, 0.1580 + 0.4236j, 0.1559 + 0.5017j],
                      [0.1580 + 0.4236j, 0.5655 + 1.1052j, 0.1535 + 0.3849j],
                      [0.1559 + 0.5017j, 0.1535 + 0.3849j, 0.5616 + 1.1212j]]) / Zbase

Ys_per_km = np.linalg.inv(Zs_per_km)

grid.lines[6].ys.values = Ys_per_km * grid.lines[6].length


# ----------------------------------------------------------------------------------------------------------------------
# Compose Yf, Yt and Ybus
# ----------------------------------------------------------------------------------------------------------------------

bus_idx_dict = grid.get_bus_index_dict()

n = grid.get_bus_number()
m = grid.get_branch_number()
Cf = np.zeros((3 * m, 3 * n), dtype=int)
Ct = np.zeros((3 * m, 3 * n), dtype=int)
Yf = np.zeros((3 * m, 3 * n), dtype=complex)
Yt = np.zeros((3 * m, 3 * n), dtype=complex)
Y = np.zeros((3 * n, 3 * n), dtype=complex)
k = -1  # branch index
idx3 = np.array([0, 1, 2])  # array that we use to generate the 3-phase indices

for elm_idx, elm in enumerate(grid.lines):
    f = bus_idx_dict[elm.bus_from]
    t = bus_idx_dict[elm.bus_to]
    k += 1

    f3 = 3 * f + idx3
    t3 = 3 * t + idx3
    k3 = 3 * k + idx3

    if elm.ys.size != 3:
        z1 = complex(elm.R, elm.X)
        z0 = complex(elm.R0, elm.X0)

        ysh1 = complex(0.0, elm.B)
        ysh0 = complex(0.0, elm.B0)

        z_abc = seq2abc(z0, z1)
        ys_abc = np.linalg.inv(z_abc)
    else:
        ys_abc = elm.ys.values

    # TODO: review that this is actually ok
    ysh_abc = seq2abc(ysh0, ysh1)

    #
    yff = ys_abc + ysh_abc / 2
    yft = - ys_abc
    ytf = - ys_abc
    ytt = ys_abc + ysh_abc / 2

    Yf[np.ix_(k3, f3)] = yff
    Yf[np.ix_(k3, t3)] = yft
    Yt[np.ix_(k3, f3)] = ytf
    Yt[np.ix_(k3, t3)] = ytt

    Y[np.ix_(f3, f3)] += yff
    Y[np.ix_(f3, t3)] += yft
    Y[np.ix_(t3, f3)] += ytf
    Y[np.ix_(t3, t3)] += ytt

    Cf[k3, f3] = 1
    Ct[k3, t3] = 1

for elm_idx, elm in enumerate(grid.transformers2w):
    f = bus_idx_dict[elm.bus_from]
    t = bus_idx_dict[elm.bus_to]
    k += 1

    f3 = 3 * f + idx3
    t3 = 3 * t + idx3
    k3 = 3 * k + idx3

    z1 = complex(elm.R, elm.X)
    z0 = complex(elm.R0, elm.X0)

    ysh1 = complex(elm.G, elm.B)
    ysh0 = complex(elm.G0, elm.B0)

    z_abc = seq2abc(z0, z1)
    ys_abc = np.linalg.inv(z_abc)

    # TODO: review that this is actually ok
    ysh_abc = seq2abc(ysh0, ysh1)

    #
    yff = ys_abc + ysh_abc / 2
    yft = - ys_abc
    ytf = - ys_abc
    ytt = ys_abc + ysh_abc / 2

    Yf[np.ix_(k3, f3)] = yff
    Yf[np.ix_(k3, t3)] = yft
    Yt[np.ix_(k3, f3)] = ytf
    Yt[np.ix_(k3, t3)] = ytt

    Y[np.ix_(f3, f3)] += yff
    Y[np.ix_(f3, t3)] += yft
    Y[np.ix_(t3, f3)] += ytf
    Y[np.ix_(t3, t3)] += ytt

    Cf[k3, f3] = 1
    Ct[k3, t3] = 1

print("Yf")
print(Yf)
print("Yt")
print(Yt)

Y2 = Cf.T @ Yf + Ct.T @ Yt

print("Y")
print(Y)

print("Y2")
print(Y2)

ok = np.allclose(Y, Y2)
print("Y=Y2:", ok)
