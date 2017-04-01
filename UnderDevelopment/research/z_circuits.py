
import numpy as np
import pandas as pd
np.set_printoptions(precision=3, linewidth=10000, suppress=True)


def make_z_i(df_br, df_bus, df_gen, df_load):
    """
    Make the augmented impedance matrix and the first iteration currents
    :param df_br: Branches DataFrame
    :param df_bus: Buses DataFrame
    :param df_gen: Generators DataFrame
    :param df_load: Loads DataFrame
    :return:
    """
    nb = len(df_bus)
    ng = len(df_gen)
    nbr = len(df_br)
    nl = len(df_load)
    SBASE = 100

    n = nb + ng
    z = np.zeros((n, n), dtype=complex)  # system matrix
    vnom = np.zeros(nb, dtype=float)  # nominal voltages
    sinj = np.zeros(nb, dtype=complex)  # power injections
    ii = np.zeros(n, dtype=complex)  # independent variables term

    bus_dict = dict()
    for i in range(nb):
        bus_dict[df_bus['name'].values[i]] = i
        vnom[i] = df_bus['Vnom'].values[i]
        z[i, i] = complex(0)

    # include the branches
    for i in range(nbr):
        f = bus_dict[df_br['bus_from'].values[i]]
        t = bus_dict[df_br['bus_to'].values[i]]

        zz = df_br['R'].values[i] + 1j * df_br['X'].values[i]
        z[f, t] = -zz
        z[t, f] = -zz
        z[f, f] += zz
        z[t, t] += zz

    # include the voltage sources
    for i in range(ng):
        t = bus_dict[df_gen['bus'].values[i]]
        z[nb + i, i] = complex(1)
        z[i, nb + i] = complex(-1)
        vnom[t] = vnom[t] * df_gen['Vset'].values[i]  # modify the bus "nominal" voltage
        ii[nb + i] = df_gen['Vset'].values[i]

    # include the loads
    for i in range(nl):
        t = bus_dict[df_load['bus'].values[i]]
        sinj[t] = complex(df_load['S'].values[i]) / SBASE
        ii[t] = np.conj(sinj[t] / vnom[t])

    print('Vnom: ', vnom)

    return z, ii, sinj, vnom


def make_z_i2(df_br, df_bus, df_gen, df_load):
    """
    Make the pseudo impedance matrix (where the voltage is known, the row contains a 1 at that node)
    :param df_br: Branches DataFrame
    :param df_bus: Buses DataFrame
    :param df_gen: Generators DataFrame
    :param df_load: Loads DataFrame
    :return:
    """
    nb = len(df_bus)
    ng = len(df_gen)
    nbr = len(df_br)
    nl = len(df_load)
    SBASE = 100

    n = nb + 1  # number of buses plus the ground node
    z = np.zeros((n, n), dtype=complex)  # system matrix
    vnom = np.zeros(n, dtype=float)  # nominal voltages
    sinj = np.zeros(n, dtype=complex)  # power injections
    ii = np.zeros(n, dtype=complex)  # independent variables term

    # set the ground node
    z[0, 0] = complex(1)

    # go through the buses and build the bus numbering dictionary
    bus_dict = dict()
    for i in range(nb):
        bus_dict[df_bus['name'].values[i]] = i + 1  # the +1 in the indices is to skip the ground node later
        vnom[i+1] = df_bus['Vnom'].values[i]  # the +1 in the indices is to skip the ground node
        z[i+1, i+1] = complex(0)  # the +1 in the indices is to skip the ground node

    # include the branches
    for i in range(nbr):
        f = bus_dict[df_br['bus_from'].values[i]]
        t = bus_dict[df_br['bus_to'].values[i]]

        zz = df_br['R'].values[i] + 1j * df_br['X'].values[i]
        z[f, t] = -zz
        z[t, f] = -zz
        z[f, f] += zz
        z[t, t] += zz

    # include the voltage sources (slacks only where the full voltage is known)
    for i in range(ng):
        t = bus_dict[df_gen['bus'].values[i]]
        row = np.zeros(n, dtype=complex)
        row[t] = 1
        z[t, :] = row  # substitute the row with an all-zero row but at t, t
        ii[t] = df_gen['Vset'].values[i]  # set the independent term to the node voltage

    # include the loads as linearized currents
    for i in range(nl):
        t = bus_dict[df_load['bus'].values[i]]
        sinj[t] = complex(df_load['S'].values[i]) / SBASE
        ii[t] = np.conj(sinj[t] / vnom[t])

    print('Vnom: ', vnom)

    return z, ii, sinj, vnom


if __name__ == '__main__':
    # branch
    # name	bus_from	bus_to	is_enabled	rate	mttf	mttr	R	X	G	B
    branches_df = pd.read_excel('lynn5buspq.xlsx', 'branch')

    # bus
    # name	is_enabled	is_slack	Vnom	Vmin	Vmax	Zf	x	y
    bus_df = pd.read_excel('lynn5buspq.xlsx', 'bus')

    # Gen
    # name	bus	P	Vset	Snom	Qmin	Qmax
    gen_df = pd.read_excel('lynn5buspq.xlsx', 'controlled_generator')

    # Load
    # name	bus	Z	I	S
    load_df = pd.read_excel('lynn5buspq.xlsx', 'load')

    nn = len(bus_df)

    # make the impedance matrix
    Z, I, S, Vnom = make_z_i(df_br=branches_df, df_bus=bus_df, df_gen=gen_df, df_load=load_df)

    print('Z:\n', Z)
    print('I:\n', I)
    print('S:\n', S)

    # first voltage solve
    V = np.linalg.solve(Z, I)

    print('V:\n', V[:nn])
    print('Vabs: ', abs(V[:nn]))

    ####################################################################################################################
    # Test 2
    ####################################################################################################################
    print('\nTest2:\n')
    # make the impedance matrix
    Z2, I2, S2, Vnom2 = make_z_i2(df_br=branches_df, df_bus=bus_df, df_gen=gen_df, df_load=load_df)

    print('Z:\n', Z2)
    print('I:\n', I2)
    print('S:\n', S2)

    # first voltage solve
    V2 = np.linalg.solve(Z2, I2)

    print('V:\n', V2)
    print('Vabs: ', abs(V2))

