from GridCal.Engine import *
from math import sqrt

if __name__ == '__main__':

    # ------------------------------------------------------------------------------------------------------------------
    # Revert the calcs
    # ------------------------------------------------------------------------------------------------------------------
    Vf = 11
    Vt = 132
    G = 0
    B = 0
    R = 0
    X = 0.115

    Sn = 30

    print()
    print('R', R)
    print('X', X)
    print('G', G)
    print('B', B)

    zsc = sqrt(R * R + 1 / (X * X))
    Vsc = 100.0 * zsc
    Pcu = R * Sn * 1000.0

    if abs(G) > 0.0 and abs(B) > 0.0:
        zl = 1.0 / complex(G, B)
        rfe = zl.real
        xm = zl.imag

        Pfe = 1000.0 * Sn / rfe

        k = 1 / (rfe * rfe) + 1 / (xm * xm)
        I0 = 100.0 * sqrt(k)
    else:
        Pfe = 1e-20
        I0 = 1e-20

    print('Vsc', Vsc)
    print('Pcu', Pcu)
    print('I0', I0)
    print('Pfe', Pfe)

    tpe2 = TransformerType(hv_nominal_voltage=Vf,
                           lv_nominal_voltage=Vt,
                           nominal_power=Sn,
                           copper_losses=Pcu,
                           iron_losses=Pfe,
                           no_load_current=I0,
                           short_circuit_voltage=Vsc,
                           gr_hv1=0.5,
                           gx_hv1=0.5)

    z2, zl2 = tpe2.get_impedances()
    # print(z2)
    # print(1/zl2)
    yl = 1/zl2

    print()
    print('R', z2.real)
    print('X', z2.imag)
    print('G', yl.real)
    print('B', yl.imag)
