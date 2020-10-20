from GridCal.Engine import *
from GridCal.Engine.Core.admittance_matrices import compute_admittances

def test1():
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE14_from_raw.gridcal'
    grid = FileOpen(fname).open()

    nc = compile_snapshot_circuit(grid)
    islands = nc.split_into_islands()
    circuit = islands[0]

    t = 0
    Y = compute_admittances(R=circuit.branch_data.R,
                            X=circuit.branch_data.X,
                            G=circuit.branch_data.G,
                            B=circuit.branch_data.B,
                            k=circuit.branch_data.k,
                            m=circuit.branch_data.m[:, t],
                            mf=circuit.branch_data.tap_f,
                            mt=circuit.branch_data.tap_t,
                            theta=circuit.branch_data.theta[:, t],
                            Beq=circuit.branch_data.Beq[:, t],
                            Cf=circuit.Cf,
                            Ct=circuit.Ct,
                            G0=circuit.branch_data.G0[:, t],
                            If=np.zeros(len(circuit.branch_data)),
                            a=circuit.branch_data.a,
                            b=circuit.branch_data.b,
                            c=circuit.branch_data.c,
                            Yshunt_bus=circuit.Yshunt_from_devices[:, t])

    m2_ = circuit.branch_data.m[:, t] + 0.05

    Y2 = compute_admittances(R=circuit.branch_data.R,
                             X=circuit.branch_data.X,
                             G=circuit.branch_data.G,
                             B=circuit.branch_data.B,
                             k=circuit.branch_data.k,
                             m=m2_,
                             mf=circuit.branch_data.tap_f,
                             mt=circuit.branch_data.tap_t,
                             theta=circuit.branch_data.theta[:, t],
                             Beq=circuit.branch_data.Beq[:, t],
                             Cf=circuit.Cf,
                             Ct=circuit.Ct,
                             G0=circuit.branch_data.G0[:, t],
                             If=np.zeros(len(circuit.branch_data)),
                             a=circuit.branch_data.a,
                             b=circuit.branch_data.b,
                             c=circuit.branch_data.c,
                             Yshunt_bus=circuit.Yshunt_from_devices[:, t])

    Ybus3, _, _ = Y.modify_taps(circuit.branch_data.m[:, t], m2_)

    ok = (Ybus3 == Y2.Ybus).data.all()
    assert ok


def test2():
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE14_from_raw.gridcal'
    grid = FileOpen(fname).open()

    nc = compile_snapshot_circuit(grid)
    islands = nc.split_into_islands()
    circuit = islands[0]

    t = 0
    Y = compute_admittances(R=circuit.branch_data.R,
                            X=circuit.branch_data.X,
                            G=circuit.branch_data.G,
                            B=circuit.branch_data.B,
                            k=circuit.branch_data.k,
                            m=circuit.branch_data.m[:, t],
                            mf=circuit.branch_data.tap_f,
                            mt=circuit.branch_data.tap_t,
                            theta=circuit.branch_data.theta[:, t],
                            Beq=circuit.branch_data.Beq[:, t],
                            Cf=circuit.Cf,
                            Ct=circuit.Ct,
                            G0=circuit.branch_data.G0[:, t],
                            If=np.zeros(len(circuit.branch_data)),
                            a=circuit.branch_data.a,
                            b=circuit.branch_data.b,
                            c=circuit.branch_data.c,
                            Yshunt_bus=circuit.Yshunt_from_devices[:, t])

    idx = circuit.transformer_idx

    m_short = circuit.branch_data.m[idx, t]
    m2_short = m_short + 0.05
    m2_long = circuit.branch_data.m[:, t].copy()
    m2_long[idx] = m2_short

    Y2 = compute_admittances(R=circuit.branch_data.R,
                             X=circuit.branch_data.X,
                             G=circuit.branch_data.G,
                             B=circuit.branch_data.B,
                             k=circuit.branch_data.k,
                             m=m2_long,
                             mf=circuit.branch_data.tap_f,
                             mt=circuit.branch_data.tap_t,
                             theta=circuit.branch_data.theta[:, t],
                             Beq=circuit.branch_data.Beq[:, t],
                             Cf=circuit.Cf,
                             Ct=circuit.Ct,
                             G0=circuit.branch_data.G0[:, t],
                             If=np.zeros(len(circuit.branch_data)),
                             a=circuit.branch_data.a,
                             b=circuit.branch_data.b,
                             c=circuit.branch_data.c,
                             Yshunt_bus=circuit.Yshunt_from_devices[:, t])

    Ybus3, _, _ = Y.modify_taps(m_short, m2_short, idx)

    ok = (Ybus3 == Y2.Ybus).data.all()
    assert ok


if __name__ == "__main__":

    # test1()
    test2()

