
from research.three_phase.Engine import *

from scipy.sparse import lil_matrix

np.set_printoptions(linewidth=100000)


def set_sub(A, cols, rows, sub_mat):
    """
    Set sub-matrix in place into sparse matrix
    :param A: Sparse matrix
    :param cols: array of columns (size m)
    :param rows: array of rows (size n)
    :param sub_mat: dense array (size n x m)
    """
    for i, a in enumerate(rows):
        for j, b in enumerate(cols):
            A[a, b] = sub_mat[i, j]


def y_bus(circuit: Circuit):
    """
    Vectorized 3-phase Y bus building
    :param circuit: Circuit instance
    :return:
    """
    n = len(circuit.buses)
    m = len(circuit.branches)

    Cf = lil_matrix((3 * m, 3 * n))
    Ct = lil_matrix((3 * m, 3 * n))

    yff = lil_matrix((3 * m, 3 * m), dtype=complex)
    yft = lil_matrix((3 * m, 3 * m), dtype=complex)
    ytf = lil_matrix((3 * m, 3 * m), dtype=complex)
    ytt = lil_matrix((3 * m, 3 * m), dtype=complex)

    bus_idx = dict()

    # compile nodes
    for k, elm in enumerate(circuit.buses):
        # store the object and its index in a dictionary
        bus_idx[elm] = k

    br_ind = np.array([0, 1, 2])

    for k, branch in enumerate(circuit.branches):

        # get the single-phase bus indices
        f_idx = bus_idx[branch.f]
        t_idx = bus_idx[branch.t]

        # expand the bus indices to the n-phase scheme
        f3 = 3 * f_idx + branch.phases_from
        t3 = 3 * t_idx + branch.phases_to

        # expand the branch index to the n-phase scheme
        b3 = 3 * k + br_ind

        # set the connectivity matrices (note that we set the values at (b3[0], f3[0]), (b3[1], f3[1]), (b3[2], f3[2])
        Cf[b3, f3] = np.ones(3, dtype=int)
        Ct[b3, t3] = np.ones(3, dtype=int)

        # get the four 3x3 primitives of the branch
        A, B, C, D, _, _ = branch.get_ABCD(Sbase=circuit.Sbase)

        # set the sub-matrices
        set_sub(A=yff, cols=b3, rows=b3, sub_mat=A)
        set_sub(A=yft, cols=b3, rows=b3, sub_mat=B)
        set_sub(A=ytf, cols=b3, rows=b3, sub_mat=C)
        set_sub(A=ytt, cols=b3, rows=b3, sub_mat=D)

    # compose Yf, Yt and Ybus
    yf = yff * Cf + yft * Ct
    yt = ytf * Cf + ytt * Ct
    ybus = Cf.transpose() * yf + Ct.transpose() * yt

    print(ybus.todense())


if __name__ == "__main__":

    P = np.array([2.5, 2.5, 2.5])
    S = np.array([2+2j, 20+2j, 40+3j])

    b1 = Bus("B1", number_of_phases=3, Vnom=10.0)
    b1.is_slack = True
    b1.add_generator(Generator("", P=P, v=1.0))

    b2 = Bus("B2", number_of_phases=3, Vnom=10.0)
    b2.add_load(LoadSIY("", S, np.zeros_like(S), np.zeros_like(S)))

    b3 = Bus("B3", number_of_phases=3, Vnom=10.0)
    # b3.add_generator(Generator("", P=P*0.5, v=1.0))

    line_type1 = LineTypeSeq(name="",
                             Z_SEQ=np.array([0.4606 + 1.7536j, 0.1808 + 0.6054j, 0.1808 + 0.6054j])/100,
                             Ysh_SEQ=np.array([0, 0, 0]))

    lne1 = Line("L1", line_type1, bus_from=b1, bus_to=b2, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=100.0)
    lne2 = Line("L2", line_type1, bus_from=b2, bus_to=b3, conn_from=[0, 1, 2], conn_to=[0, 1, 2], length=10.0)

    circuit_ = Circuit(Sbase=100)
    circuit_.buses.append(b1)
    circuit_.buses.append(b2)
    circuit_.buses.append(b3)

    circuit_.branches.append(lne1)
    circuit_.branches.append(lne2)

    y_bus(circuit=circuit_)
