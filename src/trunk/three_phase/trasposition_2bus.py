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

# add bus 2 with a load attached
bus2 = gce.Bus('Bus 2', Vnom=20)
grid.add_bus(bus2)
grid.add_load(bus2, gce.Load('load 2', P=40, Q=20))

bus1.ph_n = False
bus2.ph_n = False


# add Lines connecting the buses
line = grid.add_line(gce.Line(bus1, bus2, name='line 1-2',
                              r=0.05, x=0.11, b=0.0,
                              r0=0.05 * 2, x0=0.11 * 2, b0=0.0 * 2))
line.conn_f = np.array([0, 1, 2])  # ABC
line.conn_t = np.array([2, 0, 1])  # BAC

Zbase = (bus1.Vnom ** 2) / grid.Sbase
Zs_per_km = np.array([[0.5706 + 0.4848j, 0.1580 + 0.4236j, 0.1559 + 0.5017j],
                      [0.1580 + 0.4236j, 0.5655 + 1.1052j, 0.1535 + 0.3849j],
                      [0.1559 + 0.5017j, 0.1535 + 0.3849j, 0.5616 + 1.1212j]]) / Zbase
#
# Ys_per_km = np.linalg.pinv(Zs_per_km)
#
# grid.lines[0].ys.values = Ys_per_km * grid.lines[0].length

# ----------------------------------------------------------------------------------------------------------------------
# Compose Yf, Yt and Ybus
# ----------------------------------------------------------------------------------------------------------------------

bus_idx_dict = grid.get_bus_index_dict()

n = grid.get_bus_number()
m = grid.get_branch_number()
dim = 3
Cf = np.zeros((dim * m, dim * n), dtype=int)
Ct = np.zeros((dim * m, dim * n), dtype=int)
Yf = np.zeros((dim * m, dim * n), dtype=complex)
Yt = np.zeros((dim * m, dim * n), dtype=complex)
k = -1  # branch index
idx3 = np.array(range(dim))  # array that we use to generate the 3-phase indices

mask = np.zeros(dim * n, dtype=bool)
for i, elm in enumerate(grid.buses):
    mask[dim * i + 0] = elm.ph_a
    mask[dim * i + 1] = elm.ph_b
    mask[dim * i + 2] = elm.ph_c
    # mask[dim * i + 3] = elm.ph_n
mask_idx = np.where(mask == True)[0]

for elm_idx, elm in enumerate(grid.lines):
    f = bus_idx_dict[elm.bus_from]
    t = bus_idx_dict[elm.bus_to]
    k += 1

    f3 = dim * f + elm.conn_f
    t3 = dim * t + elm.conn_t
    kf3 = dim * k + elm.conn_f
    kt3 = dim * k + elm.conn_t

    bus_f_dim = elm.bus_from.ph_a + elm.bus_from.ph_b + elm.bus_from.ph_c + elm.bus_from.ph_n
    bus_t_dim = elm.bus_to.ph_a + elm.bus_to.ph_b + elm.bus_to.ph_c + elm.bus_to.ph_n

    if elm.ys.size != dim:
        z1 = complex(elm.R, elm.X)
        z0 = complex(elm.R0, elm.X0)

        z_abc = seq2abc(z0, z1)
        ys_abc = np.linalg.pinv(z_abc)
    else:
        ys_abc = elm.ys.values

    # TODO: review that this is actually ok
    ysh1 = complex(0.0, elm.B)
    ysh0 = complex(0.0, elm.B0)
    ysh_abc = seq2abc(ysh0, ysh1)

    #
    yff = ys_abc + ysh_abc / 2
    yft = - ys_abc
    ytf = - ys_abc
    ytt = ys_abc + ysh_abc / 2

    Yf[np.ix_(kf3, f3)] = yff
    Yf[np.ix_(kf3, t3)] = yft
    Yt[np.ix_(kt3, f3)] = ytf
    Yt[np.ix_(kt3, t3)] = ytt

    Cf[kf3, f3] = 1
    Ct[kt3, t3] = 1

print("Yf")
print(Yf)
print("Yt")
print(Yt)

Y = Cf.T @ Yf + Ct.T @ Yt

print("Y")
print(Y)



Vm1 = np.array([10, 10, 10])
Vm2 = np.array([9.95, 9.93, 9.91])
Va1 = np.array([0, -120, 120])
Va2 = Va1 - np.array([10, 9.5, 8])

V1 = Vm1 * np.exp(1j * Va1)
V2 = Vm2 * np.exp(1j * Va2)
dV = V1 - V2

V = np.r_[V1, V2]

I1 = Yf @ V
I2 = Yt @ V

print("I1", I1)
print("I2", I2)
