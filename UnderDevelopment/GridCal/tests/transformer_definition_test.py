from GridCal.Engine.CalculationEngine import *

if __name__ == '__main__':

    Vf = 20.0  # kV
    Vt = 0.4  # kV
    Sn = 0.5  # MVA
    Pcu = 6.0  # kW
    Pfe = 1.4  # kW
    I0 = 0.28  # %
    Vsc = 6.0  # %

    tpe = TransformerType(HV_nominal_voltage=Vf,
                          LV_nominal_voltage=Vt,
                          Nominal_power=Sn,
                          Copper_losses=Pcu,
                          Iron_losses=Pfe,
                          No_load_current=I0,
                          Short_circuit_voltage=Vsc,
                          GR_hv1=0.5,
                          GX_hv1=0.5)

    z, ysh = tpe.get_impedances()
    print(z)
    print(ysh)
