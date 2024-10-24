"""
This script models the admittance primitives following the PSSe and GridCal ways of modelling
This serves to understand the differences between both
"""
import numpy as np
from GridCalEngine.IO.raw.devices.transformer import RawTransformer
from GridCalEngine.Devices.Branches.transformer import Transformer2W, Bus, TapChangerTypes

# ----------------------------------------------------------------------------------------------------------------------
# PSSe modelling
# ----------------------------------------------------------------------------------------------------------------------

# Bus voltages
V1 = 220.0
V2 = 19.0

tr = RawTransformer()

tr.CM = 1
tr.CZ = 1
tr.CW = 1

tr.R1_2 = 0.000520
tr.X1_2 = 0.0247

tr.WINDV1 = 1.02275
tr.WINDV2 = 1.0

tr.ANG1 = 0.0

tr.NOMV1 = 225.005
tr.NOMV2 = 19.0

tr.RMA1 = 1.125
tr.RMI1 = 0.92050
tr.VMA1 = 1.09090
tr.VMI1 = 0.9545
tr.NTP1 = 17

# admittance primitives ---------------------------------------------------
ys = 1.0 / (tr.R1_2 + 1j * tr.X1_2)
ysh = 0j

m = tr.WINDV1 / tr.WINDV2
tau = np.deg2rad(tr.ANG1)
# tap = m * np.exp(1j * tau)

mf = 1.0
mt = 1.0

yff = (ys + ysh) / (m ** 2 * mf ** 2 * np.exp(2j * tau))
yft = -ys / (m * mf * mt)
ytf = -ys / (m * mf * mt * np.exp(2j * tau))
ytt = (ys + ysh) / (mt ** 2)

print('PSSe')
print(f"mf: {np.round(mf, 4)}, "
      f"mt: {np.round(mt, 4)}, "
      f"tap module: {np.round(m, 4)}")
print(f"yff: {np.round(yff, 4)} p.u.")
print(f"yft: {np.round(yft)} p.u.")
print(f"ytf: {np.round(ytf)} p.u.")
print(f"ytt: {np.round(ytt)} p.u.")

# ----------------------------------------------------------------------------------------------------------------------
# GridCal modelling from the PSSe data
# ----------------------------------------------------------------------------------------------------------------------

b1 = Bus(Vnom=V1)
b2 = Bus(Vnom=V2)

tr2 = Transformer2W(
    bus_from=b1, bus_to=b2,
    r=tr.R1_2,
    x=tr.X1_2,
    HV=max(tr.NOMV1, tr.NOMV2),
    LV=min(tr.NOMV1, tr.NOMV2),
    tc_total_positions=tr.NTP1,
    tc_neutral_position=9,
    tc_normal_position=9,
    tc_dV=(tr.VMA1 - tr.VMI1) / (tr.NTP1 - 1),
    tc_asymmetry_angle=90,
    tc_type=TapChangerTypes.VoltageRegulation
)

mf, mt = tr2.get_virtual_taps()

# we need to discount that PSSe includes the virtual tap inside the normal tap
tr2.tap_module = tr.WINDV1 / tr.WINDV2 / mf * mt

# admittance primitives ---------------------------------------------------

ys = 1.0 / (tr2.R + 1j * tr2.X)
ysh = (tr2.G + 1j * tr2.B) / 2

m = tr2.tap_module
tau = tr2.tap_phase
# tap = m * np.exp(1j * tau)

yff = (ys + ysh) / (m ** 2 * mf ** 2 * np.exp(2j * tau))
yft = -ys / (m * mf * mt)
ytf = -ys / (m * mf * mt * np.exp(2j * tau))
ytt = (ys + ysh) / (mt ** 2)

print('\nGridCal')
print(f"mf: {np.round(mf, 4)}, "
      f"mt: {np.round(mt, 4)}, "
      f"tap module: {np.round(m, 4)}")
print(f"yff: {np.round(yff, 4)} p.u.")
print(f"yft: {np.round(yft)} p.u.")
print(f"ytf: {np.round(ytf)} p.u.")
print(f"ytt: {np.round(ytt)} p.u.")
