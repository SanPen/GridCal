from math import sqrt

# system data
Sbase = 100  # MVA
VH = 21  # kV (bus rated voltage)
VL = 0.42  # kV (bus rated voltage)

# Transformer data
Vh = 21  # kV
Vl = 0.42  # kV
Sn = 0.25  # MVA
Pcu = 2.35  # kW
Pfe = 0.27  # kW
I0 = 1.0  # %
Vsc = 4.6  # %

# Series impedance -----------------------------------------------------------------------------------------------------
zsc = Vsc / 100.0  # p.u.
rsc = (Pcu / 1000.0) / Sn  # p.u.
if rsc < zsc:
    xsc = sqrt(zsc ** 2 - rsc ** 2)  # p.u.
else:
    xsc = 0.0
zs = rsc + 1j * xsc  # p.u.

# Shunt impedance (leakage) --------------------------------------------------------------------------------------------
if Pfe > 0.0 and I0 > 0.0:

    rfe = Sn / (Pfe / 1000.0)  # p.u.
    zm = 1.0 / (I0 / 100.0)  # p.u.
    val = (1.0 / (zm ** 2)) - (1.0 / (rfe ** 2))  # p.u.
    if val > 0:
        xm = 1.0 / sqrt(val)
        rm = sqrt(xm * xm - zm * zm)  # p.u.
    else:
        xm = 0.0
        rm = 0.0

else:

    rm = 0.0
    xm = 0.0

zsh = rm + 1j * xm

print('-' * 100)
print('Impedances in machine base')
print('Zseries:', zs, 'p.u.')
print('Yshunt:', 1.0 / zsh, 'p.u.')

# pass impedances from per unit in machine base to ohms ----------------------------------------------------------------

ZbaseHv = (Vh * Vh) / Sn
ZbaseLv = (Vl * Vl) / Sn

ZseriesHv = zs / 2 * ZbaseHv  # Ohm
ZseriesLv = zs / 2 * ZbaseLv  # Ohm
ZshuntHv = zsh / 2 * ZbaseHv  # Ohm
ZshuntLv = zsh / 2 * ZbaseLv  # Ohm

print('-' * 100)
print('Impedances in ohms')
print('Zseries:', ZseriesHv + ZseriesLv, 'Ohm')
print('Yshunt:', 1.0 / (ZshuntHv + ZshuntLv), 'S')

# pass impedances to system base ---------------------------------------------------------------------------------------

ZbaseHvSys = (VH * VH) / Sbase
ZbaseLvSys = (VL * VL) / Sbase

Zseries = ZseriesHv / ZbaseHvSys + ZseriesLv / ZbaseLvSys
Zshunt = ZshuntHv / ZbaseHvSys + ZshuntLv / ZbaseLvSys
Yshunt = 1 / Zshunt

print('-' * 100)
print('Impedances in system base')
print('Zseries:', Zseries, 'p.u.')
print('Yshunt:', Yshunt, 'p.u.')

