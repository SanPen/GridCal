from GridCal.Engine import *


Vhv = 24  # primary voltage in kV
Vlv = 0.42  # secondary voltage kV
Sn = 100  # nominal power in MVA
Psc = 300  # short circuit power (copper losses) kW
P0 = 100  # no load power (iron losses) kW
V0 = 0.8  # no load voltage in %
Vsc = 8  # short-circuit voltage in %

obj = TransformerType(hv_nominal_voltage=Vhv,
                      lv_nominal_voltage=Vlv,
                      nominal_power=Sn,
                      copper_losses=Psc,
                      short_circuit_voltage=Vsc,
                      iron_losses=P0,
                      no_load_current=V0,
                      gr_hv1=0.5, gx_hv1=0.5)

Sbase = 100
z_series, zsh = obj.get_impedances()

# Change the base to the system base power
base_change = obj.rating / Sbase
z_series *= base_change
zsh *= base_change

print(z_series, 'Ys ->', 1 / z_series)
print(zsh, '-> y_sh ->', 1 / zsh)


