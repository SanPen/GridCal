class TransformerType:

    def __init__(self, HV_nominal_voltage, LV_nominal_voltage, Nominal_power, Copper_losses, Iron_losses,
                 No_load_current, Short_circuit_voltage, GR_hv1, GX_hv1, name='TransformerType'):
        """
        Constructor
        @param HV_nominal_voltage: High voltage side nominal voltage (kV)
        @param LV_nominal_voltage: Low voltage side nominal voltage (kV)
        @param Nominal_power: Transformer nominal power (MVA)
        @param Copper_losses: Copper losses (kW)
        @param Iron_losses: Iron Losses (kW)
        @param No_load_current: No load current (%)
        @param Short_circuit_voltage: Short circuit voltage (%)
        @param GR_hv1:
        @param GX_hv1:
        """

        self.name = name

        self.type_name = 'TransformerType'

        self.properties_with_profile = None

        self.HV_nominal_voltage = HV_nominal_voltage

        self.LV_nominal_voltage = LV_nominal_voltage

        self.Nominal_power = Nominal_power

        self.Copper_losses = Copper_losses

        self.Iron_losses = Iron_losses

        self.No_load_current = No_load_current

        self.Short_circuit_voltage = Short_circuit_voltage

        self.GR_hv1 = GR_hv1

        self.GX_hv1 = GX_hv1

    def get_impedances(self):
        """
        Compute the branch parameters of a transformer from the short circuit
        test values
        @return:
            leakage_impedance: Series impedance
            magnetizing_impedance: Shunt impedance
        """
        Uhv = self.HV_nominal_voltage

        Ulv = self.LV_nominal_voltage

        Sn = self.Nominal_power

        Pcu = self.Copper_losses

        Pfe = self.Iron_losses

        I0 = self.No_load_current

        Usc = self.Short_circuit_voltage

        # Nominal impedance HV (Ohm)
        Zn_hv = Uhv * Uhv / Sn

        # Nominal impedance LV (Ohm)
        Zn_lv = Ulv * Ulv / Sn

        # Short circuit impedance (p.u.)
        zsc = Usc / 100

        # Short circuit resistance (p.u.)
        rsc = (Pcu / 1000) / Sn

        # Short circuit reactance (p.u.)
        xsc = sqrt(zsc * zsc - rsc * rsc)

        # HV resistance (p.u.)
        rcu_hv = rsc * self.GR_hv1

        # LV resistance (p.u.)
        rcu_lv = rsc * (1 - self.GR_hv1)

        # HV shunt reactance (p.u.)
        xs_hv = xsc * self.GX_hv1

        # LV shunt reactance (p.u.)
        xs_lv = xsc * (1 - self.GX_hv1)

        # Shunt resistance (p.u.)
        rfe = Sn / (Pfe / 1000)

        # Magnetization impedance (p.u.)
        zm = 1 / (I0 / 100)

        # Magnetization reactance (p.u.)
        if rfe > zm:
            xm = 1 / sqrt(1 / (zm * zm) - 1 / (rfe * rfe))
        else:
            xm = 0  # the square root cannot be computed

        # Calculated parameters in per unit
        leakage_impedance = rsc + 1j * xsc
        magnetizing_impedance = rfe + 1j * xm

        return leakage_impedance, magnetizing_impedance


