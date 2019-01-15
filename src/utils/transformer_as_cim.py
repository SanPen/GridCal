from GridCal.Engine.calculation_engine import *


def get_cim_equivalent(name, Vhv, Vlv, Sn, Pcu_, Pfe_, I0_, Vsc_):
    """
    Print CIM definition of the transformer
    :param name: Name of the transformer
    :param Vhv: High voltage kV
    :param Vlv: Low voltage kV
    :param Sn: Nominal power in MVA
    :param Pcu_: Copper losses (load losses) kW
    :param Pfe_: Iron losses (no-load losses) kW
    :param I0_: No-load current
    :param Vsc_: Short circuit voltage in %
    """

    tpe = TransformerType(hv_nominal_voltage=Vhv,
                          lv_nominal_voltage=Vlv,
                          nominal_power=Sn,
                          copper_losses=Pcu_,
                          iron_losses=Pfe_,
                          no_load_current=I0_,
                          short_circuit_voltage=Vsc_,
                          gr_hv1=0.5,
                          gx_hv1=0.5)

    zs, zsh = tpe.get_impedances()
    if zsh != 0:
        ysh = 1 / zsh
    else:
        ysh = complex(0, 0)

    # Compute the base impedances to pass the per unit values to Ohm and S
    Zb_hv = Vhv * Vhv / Sn
    Zb_lv = Vlv * Vlv / Sn

    print()
    print('-' * 80)
    print(name)
    print('-' * 80)

    print('Zseries:', zs, 'p.u.')
    print('Zshunt:', zsh, 'p.u.')
    print()
    print('PowerTransformer')
    print('\tname:', name)

    print()
    print('TransformerEnd')
    print('\tID: HV')
    print('\tBaseVoltage:', Vhv, 'kV')
    print('\tratedS:', Sn / 2, 'MVA')
    print('\tr:', zs.real / 2 * Zb_hv, 'Ohm')
    print('\tx:', zs.imag / 2 * Zb_hv, 'Ohm')
    print('\tg:', ysh.real / 2 / Zb_hv, 'S')
    print('\tb:', ysh.imag / 2 / Zb_hv, 'S')

    print()
    print('TransformerEnd')
    print('\tID: LV')
    print('\tBaseVoltage:', Vlv, 'kV')
    print('\tratedS:', Sn / 2, 'MVA')
    print('\tr:', zs.real / 2 * Zb_lv, 'Ohm')
    print('\tx:', zs.imag / 2 * Zb_lv, 'Ohm')
    print('\tg:', ysh.real / 2 / Zb_lv, 'S')
    print('\tb:', ysh.imag / 2 / Zb_lv, 'S')


if __name__ == '__main__':

    get_cim_equivalent(name='Schneider MIN200011559700000 (2 MVA)',
                       Vhv=11, Vlv=0.4, Sn=2.0, Pcu_=6.0, Pfe_=0.0, I0_=0.0, Vsc_=6.25)

    get_cim_equivalent(name='Schneider MIN080011559700000 (0.8 MVA)',
                       Vhv=11, Vlv=0.4, Sn=0.8, Pcu_=6.0, Pfe_=0.0, I0_=0.0, Vsc_=5.0)


    """
    Ormazabal
    Potencia asignada [kVA] 50 100 160 250 400 630 800 1000 1250 1600 2000 2500*
    Tensión asignada (Ur) Primaria [kV] < 24
    Secundaria en vacío [V] 420
    Grupo de Conexión Dyn11
    Pérdidas en Vacío - P0 [W] Lista A0 90 145 210 300 430 600 650 770 950 1200 1450 1750
    Pérdidas en Carga - Pk [W] Lista Bk 875 1475 2000 2750 3850 5400 7000 9000 11000 14000 18000 22000
    
    """

    Sn =  np.array([50, 100, 160, 250, 400, 630, 800, 1000, 1250, 1600, 2000, 2500]) / 1000
    Pfe = np.array([90, 145, 210, 300, 430, 600, 650, 770,  950,  1200, 1450, 1750]) / 1000
    Pcu = np.array([90, 145, 210, 300, 430, 600, 650, 770, 950, 1200, 1450, 1750]) / 1000
    Vsc = np.array([4, 4, 4, 4, 4, 4, 6, 6, 6, 6, 6, 6])
    for i in range(len(Sn)):
        get_cim_equivalent(name='Ormazabal (' + str(Sn[i]) + ' MVA)',
                           Vhv=11, Vlv=0.4, Sn=Sn[i], Pcu_=Pcu[i], Pfe_=Pfe[i], I0_=0.0, Vsc_=Vsc[i])
