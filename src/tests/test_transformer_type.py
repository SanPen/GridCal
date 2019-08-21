from GridCal.Engine.Devices.transformer import TransformerType
# from math import sqrt


def test_transformer_type():

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


# def template_from_impedances():
#
#     # generate the template
#
#     Vhv = 24  # primary voltage in kV
#     Vlv = 0.42  # secondary voltage kV
#     Sn = 100  # nominal power in MVA
#     Pcu = 300  # short circuit power (copper losses) kW
#     Pfe = 100  # no load power (iron losses) kW
#     I0 = 0.8  # no load voltage in %
#     Vsc = 8  # short-circuit voltage in %
#
#     # Series impedance
#     zsc = Vsc / 100.0
#     rsc = (Pcu / 1000.0) / Sn
#     xsc = sqrt(zsc ** 2 - rsc ** 2)
#     z_series = rsc + 1j * xsc
#
#     # Shunt impedance (leakage)
#     if Pfe > 0.0 and I0 > 0.0:
#
#         rfe = Sn / (Pfe / 1000.0)
#         zm = 1.0 / (I0 / 100.0)
#         val = (1.0 / (zm ** 2)) - (1.0 / (rfe ** 2))
#         if val > 0:
#             xm = 1.0 / sqrt((1.0 / (zm ** 2)) - (1.0 / (rfe ** 2)))
#             rm = sqrt(xm * xm - zm * zm)
#         else:
#             xm = 0.0
#             rm = 0.0
#
#     else:
#
#         rm = 0.0
#         xm = 0.0
#
#     zsh = rm + 1j * xm
#
#     # -----------------------------------------------------------------------
#     # revert
#
#     R = z_series.real
#     X = z_series.imag
#     G = zsh.real
#     B = zsh
#
#     zsc_2 = sqrt(R * R + X * X)
#     Vsc_2 = 100.0 * zsc_2
#     Pcu_2 = R * Sn * 1000.0
#
#     if abs(G) > 0.0 and abs(B) > 0.0:
#         zl = 1.0 / complex(G, B)
#         rm = zl.real
#         xm = zl.imag
#
#         rfe = sqrt(1.0 / (1.0 / (rm * rm + xm * xm) - 1.0 / (xm * xm)))
#
#         Pfe_2 = 1000.0 * Sn / rfe
#
#         k = 1 / (rfe * rfe) + 1 / (xm * xm)
#         I0_2 = 100.0 * sqrt(k)
#     else:
#         Pfe_2 = 0
#         I0_2 = 0
#
#     eps = 1e-6
#     assert abs(Pcu - Pcu_2) < eps
#     assert abs(Vsc - Vsc_2) < eps
#
#     assert abs(Pfe - Pfe_2) < eps
#     assert abs(I0 - I0_2) < eps


if __name__ == '__main__':
    # template_from_impedances()

    test_transformer_type()
