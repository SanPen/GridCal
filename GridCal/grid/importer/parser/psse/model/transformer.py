from _warnings import warn

from GridCal.grid.model.branch import Branch


class PSSeTransformer:

    def __init__(self, data, version):
        """
        I The bus number, or extended bus name enclosed in single quotes (refer to
            Extended Bus Names), of the bus to which Winding 1 is connected. The trans-
            former’s magnetizing admittance is modeled on Winding 1. Winding 1 is the only
            winding of a two-winding transformer for which tap ratio or phase shift angle may be
            adjusted by the power flow solution activities; any winding(s) of a three-winding
            transformer may be adjusted. No default is allowed.
        J The bus number, or extended bus name enclosed in single quotes, of the bus to
            which Winding 2 is connected. No default is allowed.
        K The bus number, or extended bus name enclosed in single quotes, of the bus to
            which Winding 3 is connected. Zero is used to indicate that no third winding is
            present (i.e., that a two-winding rather than a three-winding transformer is being
            specified). K = 0 by default.
        CKT One- or two-character uppercase non-blank alphanumeric transformer circuit identi-
            fier; the first character of CKT must not be an ampersand ( & ), at sign ( @ ), or
            asterisk ( * ); refer to Multi-Section Line Grouping Data and Section 6.17.2, Outage
            Statistics Data File Contents. CKT = 1 by default.
        CW The winding data I/O code defines the units in which the turns ratios WINDV1,
            WINDV2 and WINDV3 are specified (the units of RMAn and RMIn are also
            governed by CW when |CODn| is 1 or 2):
            1 for off-nominal turns ratio in pu of winding bus base voltage
            2 for winding voltage in kV
            3 for off-nominal turns ratio in pu of nominal winding voltage, 
            NOMV1, NOMV2 and NOMV3.
            CW = 1 by default.
        CZ  The impedance data I/O code defines the units in which the winding impedances
            R1-2, X1-2, R2-3, X2-3, R3-1 and X3-1 are specified:

            1 for resistance and reactance in pu on system MVA base and  winding voltage base

            2 for resistance and reactance in pu on a specified MVA base and winding voltage base

            3 for transformer load loss in watts and impedance magnitude in pu on a specified
              MVA base and winding voltage base.

            In specifying transformer leakage impedances, the base voltage values are always
            the nominal winding voltages that are specified on the third, fourth and fifth records
            of the transformer data block (NOMV1, NOMV2 and NOMV3). If the default NOMVn
            is not specified, it is assumed to be identical to the winding n bus base voltage.
            CZ = 1 by default.
        CM The magnetizing admittance I/O code defines the units in which MAG1 and MAG2 are specified:
            1 for complex admittance in pu on system MVA base and Winding 1 
            bus voltage base
            2 for no load loss in watts and exciting current in pu on Winding 1 to 
            two MVA base (SBASE1-2) and nominal Winding 1 voltage, NOMV1.
            CM = 1 by default.
        MAG1, MAG2: The transformer magnetizing admittance connected to ground at bus I.
            When CM is 1, MAG1 and MAG2 are the magnetizing conductance and suscep-
            tance, respectively, in pu on system MVA base and Winding 1 bus voltage base.
            When a non-zero MAG2 is specified, it should be entered as a negative quantity.
            When CM is 2, MAG1 is the no load loss in watts and MAG2 is the exciting current
            in pu on Winding 1 to two MVA base (SBASE1-2) and nominal Winding 1 voltage
            (NOMV1). For three-phase transformers or three-phase banks of single phase
            transformers, MAG1 should specify the three-phase no-load loss. When a non-zero
            MAG2 is specified, it should be entered as a positive quantity.
            MAG1 = 0.0 and MAG2 = 0.0 by default.
        NMETR The non-metered end code of either 1 (for the Winding 1 bus) or 2 (for the Winding 2 bus).
            In addition, for a three-winding transformer, 3 (for the Winding 3 bus) is a valid
            specification of NMETR. NMETR = 2 by default.
        NAME Alphanumeric identifier assigned to the transformer. NAME may be up to twelve
            characters and may contain any combination of blanks, uppercase letters, numbers
            and special characters. NAME must be enclosed in single or double quotes if it
            contains any blanks or special characters. NAME is twelve blanks by default.
        STAT Transformer status of one for in-service and zero for out-of-service.
            In addition, for a three-winding transformer, the following values of STAT provide for
            one winding out-of-service with the remaining windings in-service:
            2 -> for only Winding 2 out-of-service
            3 -> for only Winding 3 out-of-service
            4 -> for only Winding 1 out-of-service
            STAT = 1 by default.
        Oi: An owner number (1 through 9999). Each transformer may have up to four owners.
            By default, O1 is the owner to which bus I is assigned and O2, O3, and O4 are zero.
        Fi: The fraction of total ownership assigned to owner Oi; each Fi must be positive. The
            Fi values are normalized such that they sum to 1.0 before they are placed in the
            working case. By default, each Fi is 1.0.
        VECGRP: Alphanumeric identifier specifying vector group based on transformer winding
            connections and phase angles. VECGRP value is used for information purpose
            only. VECGRP is 12 blanks by default

        ----------------------------------------------------------------------------------------------
        The first three data items on the second record are read for both two- and three-winding trans-
        formers; the remaining data items are used only for three-winding transformers:

        R1-2, X1-2 The measured impedance of the transformer between the buses to which its first
            and second windings are connected.
            When CZ is 1, they are the resistance and reactance, respectively, in pu on system
            MVA base and winding voltage base.
            When CZ is 2, they are the resistance and reactance, respectively, in pu on Winding
            1 to 2 MVA base (SBASE1-2) and winding voltage base.
            When CZ is 3, R1-2 is the load loss in watts, and X1-2 is the impedance magnitude
            in pu on Winding 1 to 2 MVA base (SBASE1-2) and winding voltage base. For
            three-phase transformers or three-phase banks of single phase transformers, R1-2
            should specify the three-phase load loss.
            R1-2 = 0.0 by default, but no default is allowed for X1-2.
        SBASE1-2 The Winding 1 to 2 three-phase base MVA of the transformer. SBASE1-2 = SBASE
            (the system base MVA) by default.
        R2-3, X2-3 The measured impedance of a three-winding transformer between the buses to
            which its second and third windings are connected; ignored for a two-winding
            transformer.
            When CZ is 1, they are the resistance and reactance, respectively, in pu on system
            MVA base and winding voltage base.
            When CZ is 2, they are the resistance and reactance, respectively, in pu on Winding
            2 to 3 MVA base (SBASE2-3) and winding voltage base.
            When CZ is 3, R2-3 is the load loss in watts, and X2-3 is the impedance magnitude
            in pu on Winding 2 to 3 MVA base (SBASE2-3) and winding voltage base. For
            three-phase transformers or three-phase banks of single phase transformers, R2-3
            should specify the three-phase load loss.
            R2-3 = 0.0 by default, but no default is allowed for X2-3.
        SBASE2-3 The Winding 2 to 3 three-phase base MVA of a three-winding transformer; ignored
            for a two-winding transformer. SBASE2-3 = SBASE (the system base MVA) by
            default.
        R3-1, X3-1 The measured impedance of a three-winding transformer between the buses to
            which its third and first windings are connected; ignored for a two-winding
            transformer.
            When CZ is 1, they are the resistance and reactance, respectively, in pu on system
            MVA base and winding voltage base.
            When CZ is 2, they are the resistance and reactance, respectively, in pu on Winding
            3 to 1 MVA base (SBASE3-1) and winding voltage base.
            When CZ is 3, R3-1 is the load loss in watts, and X3-1 is the impedance magnitude
            in pu on Winding 3 to 1 MVA base (SBASE3-1) and winding voltage base. For
            three-phase transformers or three-phase banks of single phase transformers, R3-1
            should specify the three-phase load loss.
            R3-1 = 0.0 by default, but no default is allowed for X3-1.
        SBASE3-1 The Winding 3 to 1 three-phase base MVA of a three-winding transformer; ignored
            for a two-winding transformer. SBASE3-1 = SBASE (the system base MVA) by

        VMSTAR The voltage magnitude at the hidden star point bus; entered in pu. VMSTAR = 1.0
            by default.
        ANSTAR The bus voltage phase angle at the hidden star point bus; entered in degrees.
            ANSTAR = 0.0 by default.

        ----------------------------------------------------------------------------------------------
        All data items on the third record are read for both two- and three-winding transformers:

        WINDV1: When CW is 1, WINDV1 is the Winding 1 off-nominal turns ratio in pu of Winding 1
            bus base voltage; WINDV1 = 1.0 by default.
            When CW is 2, WINDV1 is the actual Winding 1 voltage in kV; WINDV1 is equal to
            the base voltage of bus I by default.
            When CW is 3, WINDV1 is the Winding 1 off-nominal turns ratio in pu of nominal
            Winding 1 voltage, NOMV1; WINDV1 = 1.0 by default.
        NOMV1 The nominal (rated) Winding 1 voltage base in kV, or zero to indicate that nominal
            Winding 1 voltage is assumed to be identical to the base voltage of bus I. NOMV1 is
            used in converting magnetizing data between physical units and per unit admittance
            values when CM is 2. NOMV1 is used in converting tap ratio data between values in
            per unit of nominal Winding 1 voltage and values in per unit of Winding 1 bus base
            voltage when CW is 3. NOMV1 = 0.0 by default.
        ANG1 The winding one phase shift angle in degrees. For a two-winding transformer,
            ANG1 is positive when the winding one bus voltage leads the winding two bus
            voltage; for a three-winding transformer, ANG1 is positive when the winding one
            bus voltage leads the T (or star) point bus voltage. ANG1 must be greater than -
            180.0o and less than or equal to +180.0o. ANG1 = 0.0 by default.
        RATA1, RATB1, RATC1: Winding 1’s three three-phase ratings, entered in either MVA or current expressed
            as MVA, according to the value specified for XFRRAT specified on the first data
            record (refer to Case Identification Data). RATA1 = 0.0, RATB1 = 0.0 and
            RATC1 = 0.0 (bypass loading limit check for this transformer winding) by default.
        COD1 The transformer control mode for automatic adjustments of the Winding 1 tap or
            phase shift angle during power flow solutions:
                0 for no control (fixed tap and fixed phase shift)
                ±1  for voltage control
                ±2  for reactive power flow control
                ±3  for active power flow control
                ±4  for control of a dc line quantity (valid only for two-winding  transformers)
                ±5  for asymmetric active power flow control.
            If the control mode is entered as a positive number, automatic adjustment of this
            transformer winding is enabled when the corresponding adjustment is activated
            during power flow solutions; a negative control mode suppresses the automatic
            adjustment of this transformer winding. COD1 = 0 by default.

        CONT1: The bus number, or extended bus name enclosed in single quotes (refer to
            Extended Bus Names), of the bus for which voltage is to be controlled by the trans-
            former turns ratio adjustment option of the power flow solution activities when
            COD1 is 1. CONT1 should be non-zero only for voltage controlling transformer
            windings.
            CONT1 may specify a bus other than I, J, or K; in this case, the sign of CONT1
            defines the location of the controlled bus relative to the transformer winding. If
            CONT1 is entered as a positive number, or a quoted extended bus name, the ratio
            is adjusted as if bus CONT1 is on the Winding 2 or Winding 3 side of the trans-
            former; if CONT1 is entered as a negative number, or a quoted extended bus name
            with a minus sign preceding the first character, the ratio is adjusted as if bus
            |CONT1| is on the Winding 1 side of the transformer. CONT1 = 0 by default.
        RMA1, RMI1:  When |COD1| is 1, 2 or 3, the upper and lower limits, respectively, of one of the
            following:
            • Off-nominal turns ratio in pu of Winding 1 bus base voltage when |COD1| is
            1 or 2 and CW is 1; RMA1 = 1.1 and RMI1 = 0.9 by default.
            • Actual Winding 1 vo ltage in kV when |COD1| is 1 o r 2 and CW is 2 . No
            default is allowed.
            • Off-nominal turns ratio in pu of nominal Winding 1 voltage (NOMV1) when
            |COD1| is 1 or 2 and CW is 3; RMA1 = 1.1 and RMI1 = 0.9 by default.
            • Phase shift angle in degrees when |COD1| is 3. No default is allowed.
            Not used when |COD1| is 0 or 4; RMA1 = 1.1 and RMI1 = 0.9 by default.
        VMA1, VMI1:  When |COD1| is 1, 2 or 3, the upper and lower limits, respectively, of one of the
            following:
            • Voltage at the controlled bus (bus |CONT1|) in pu when |COD1| is 1. 
            VMA1 = 1.1 and VMI1 = 0.9 by default.
            • Reactive power flow into the transformer at the Winding 1 bus end in Mvar
            when |COD1| is 2. No default is allowed.
            • Active power flow into the transformer at the Winding 1 bus end in MW when
            |COD1| is 3. No default is allowed.
            Not used when |COD1| is 0 or 4; VMA1 = 1.1 and VMI1 = 0.9 by default.
        NTP1: The number of tap positions available; used when COD1 is 1 or 2. NTP1 must be
            between 2 and 9999. NTP1 = 33 by default.
        TAB1: The number of a transformer impedance correction table if this transformer
            winding’s impedance is to be a function of either off-nominal turns ratio or phase
            shift angle (refer to Transformer Impedance Correction Tables), or 0 if no trans-
            former impedance correction is to be applied to this transformer winding. TAB1 = 0
            by default.
        CR1, CX1: The load drop compensation impedance for voltage controlling transformers
            entered in pu on system base quantities; used when COD1 is 1. CR1 + j CX1 = 0.0
            by default.
        CNXA1: Winding connection angle in degrees; used when COD1 is 5. There are no restrictions
            on the value specified for CNXA1; if it is outside of the range from -90.0 to
            +90.0, CNXA1 is normalized to within this range. CNXA1 = 0.0 by default.

        ----------------------------------------------------------------------------------------------
        The first two data items on the fourth record are read for both two- and three-winding transformers;
        the remaining data items are used only for three-winding transformers:

        WINDV2:  When CW is 1, WINDV2 is the Winding 2 off-nominal turns ratio in pu of Winding 2
            bus base voltage; WINDV2 = 1.0 by default.
            When CW is 2, WINDV2 is the actual Winding 2 voltage in kV; WINDV2 is equal to
            the base voltage of bus J by default.
            When CW is 3, WINDV2 is the Winding 2 off-nominal turns ratio in pu of nominal
            Winding 2 voltage, NOMV2; WINDV2 = 1.0 by default.
        NOMV2 The nominal (rated) Winding 2 voltage base in kV, or zero to indicate that nominal
            Winding 2 voltage is assumed to be identical to the base voltage of bus J. NOMV2
            is used in converting tap ratio data between values in per unit of nominal Winding 2
            voltage and values in per unit of Winding 2 bus base voltage when CW is 3.
            NOMV2 = 0.0 by default.
        ANG2 The winding two phase shift angle in degrees. ANG2 is ignored for a two-winding
            transformer. For a three-winding transformer, ANG2 is positive when the winding
            two bus voltage leads the T (or star) point bus voltage. ANG2 must be greater than
            -180.0o and less than or equal to +180.0o. ANG2 = 0.0 by default.
        RATA2, RATB2, RATC2: Winding 2’s three three-phase ratings, entered in either MVA or current expressed
            as MVA, according to the value specified for XFRRAT specified on the first data
            record (refer to Case Identification Data). RATA2 = 0.0, RATB2 = 0.0 and
            RATC2 = 0.0 (bypass loading limit check for this transformer winding) by default.
        COD2: The transformer control mode for automatic adjustments of the Winding 2 tap or
            phase shift angle during power flow solutions:
                0    for no control (fixed tap and fixed phase shift)
                ±1   for voltage control
                ±2   for reactive power flow control
                ±3   for active power flow control
                ±5   for asymmetric active power flow control
            If the control mode is entered as a positive number, automatic adjustment of this
            transformer winding is enabled when the corresponding adjustment is activated
            during power flow solutions; a negative control mode suppresses the automatic
            adjustment of this transformer winding. COD2 = 0 by default.
        CONT2:  The bus number, or extended bus name enclosed in single quotes (refer to
            Extended Bus Names), of the bus for which voltage is to be controlled by the trans-
            former turns ratio adjustment option of the power flow solution activities when
            COD2 is 1. CONT2 should be non-zero only for voltage controlling transformer
            windings.
            CONT2 may specify a bus other than I, J, or K; in this case, the sign of CONT2
            defines the location of the controlled bus relative to the transformer winding. If
            CONT2 is entered as a positive number, or a quoted extended bus name, the ratio
            is adjusted as if bus CONT2 is on the Winding 1 or Winding 3 side of the trans-
            former; if CONT2 is entered as a negative number, or a quoted extended bus name
            with a minus sign preceding the first character, the ratio is adjusted as if bus
            |CONT2| is on the Winding 2 side of the transformer. CONT2 = 0 by default.

        RMA2, RMI2:  When |COD2| is 1, 2 or 3, the upper and lower limits, respectively, of one of the
            following:
            • Off-nominal turns ratio in pu of Winding 2 bus base voltage when |COD2| is
            1 or 2 and CW is 1; RMA2 = 1.1 and RMI2 = 0.9 by default.
            • Actual Winding 2 voltage in kV when |COD2| is 1 or 2 and CW is 2. No default
            is allowed.
            • Off-nominal turns ratio in pu o f nominal Winding 2 voltage (NOMV2) when
            |COD2| is 1 or 2 and CW is 3; RMA2 = 1.1 and RMI2 = 0.9 by default.
            • Phase shift angle in degrees when |COD2| is 3. No default is allowed.
            Not used when |COD2| is 0; RMA2 = 1.1 and RMI2 = 0.9 by default.
        VMA2, VMI2:   When |COD2| is 1, 2 or 3, the upper and lower limits, respectively, of one of the
            following:
            • Voltage at the controlled bus (bus |CONT2|) in pu when |COD2| is 1.
            VMA2 = 1.1 and VMI2 = 0.9 by default.
            • Reactive power flow into the transformer at the Winding 2 bus end in Mvar
            when |COD2| is 2. No default is allowed.
            • Active power flow into the transformer at the Winding 2 bus end in MW when
            |COD2| is 3. No default is allowed.
            Not used when |COD2| is 0; VMA2 = 1.1 and VMI2 = 0.9 by default.
        NTP2 The number of tap positions available; used when COD2 is 1 or 2. NTP2 must be
            between 2 and 9999. NTP2 = 33 by default.
        TAB2 The number of a transformer impedance correction table if this transformer
            winding’s impedance is to be a function of either off-nominal turns ratio or phase
            shift angle (refer to Transformer Impedance Correction Tables), or 0 if no trans-
            former impedance correction is to be applied to this transformer winding. TAB2 = 0
            by default.
        CR2, CX2 The load drop compensation impedance for voltage controlling transformers
            entered in pu on system base quantities; used when COD2 is 1. CR2 + j CX2 = 0.0
            by default.
        CNXA2 Winding connection angle in degrees; used when COD2 is 5. There are no restrictions
            on the value specified for CNXA2; if it is outside of the range from -90.0 to
            +90.0, CNXA2 is normalized to within this range. CNXA2 = 0.0 by default.
            The fifth data record is specified only for three-winding transformers:
        WINDV3: When CW is 1, WINDV3 is the Winding 3 off-nominal turns ratio in pu of Winding 3
            bus base voltage; WINDV3 = 1.0 by default.
            When CW is 2, WINDV3 is the actual Winding 3 voltage in kV; WINDV3 is equal to
            the base voltage of bus K by default.
            When CW is 3, WINDV3 is the Winding 3 off-nominal turns ratio in pu of nominal
            Winding 3 voltage, NOMV3; WINDV3 = 1.0 by default.

        NOMV3 The nominal (rated) Winding 3 voltage base in kV, or zero to indicate that nominal
            Winding 3 voltage is assumed to be identical to the base voltage of bus K. NOMV3
            is used in converting tap ratio data between values in per unit of nominal Winding 3
            voltage and values in per unit of Winding 3 bus base voltage when CW is 3. NOMV3
            = 0.0 by default.
        ANG3 The winding three phase shift angle in degrees. ANG3 is positive when the winding
            three bus voltage leads the T (or star) point bus voltage. ANG3 must be greater
            than -180.0o and less than or equal to +180.0o. ANG3 = 0.0 by default.
        RATA3, RATB3, RATC3 Winding 3’s three three-phase ratings, entered in either MVA or current expressed
            as MVA, according to the value specified for XFRRAT specified on the first data
            record (refer to Case Identification Data). RATA3 = 0.0, RATB3 = 0.0 and
            RATC3 = 0.0 (bypass loading limit check for this transformer winding) by default.
        COD3 The transformer control mode for automatic adjustments of the Winding 3 tap or
            phase shift angle during power flow solutions:
            0    for no control (fixed tap and fixed phase shift)
            ±1   for voltage control
            ±2   for reactive power flow control
            ±3   for active power flow control
            ±5   for asymmetric active power flow control.

            If the control mode is entered as a positive number, automatic adjustment of this
            transformer winding is enabled when the corresponding adjustment is activated
            during power flow solutions; a negative control mode suppresses the automatic
            adjustment of this transformer winding. COD3 = 0 by default.
        CONT3:   The bus number, or extended bus name enclosed in single quotes (refer to
            Extended Bus Names), of the bus for which voltage is to be controlled by the trans-
            former turns ratio adjustment option of the power flow solution activities when
            COD3 is 1. CONT3 should be non-zero only for voltage controlling transformer
            windings.
            CONT3 may specify a bus other than I, J, or K; in this case, the sign of CONT3
            defines the location of the controlled bus relative to the transformer winding. If
            CONT3 is entered as a positive number, or a quoted extended bus name, the ratio
            is adjusted as if bus CONT3 is on the Winding 1 or Winding 2 side of the trans-
            former; if CONT3 is entered as a negative number, or a quoted extended bus name
            with a minus sign preceding the first character, the ratio is adjusted as if bus
            |CONT3| is on the Winding 3 side of the transformer. CONT3 = 0 by default.
        RMA3, RMI3:   When |COD3| is 1, 2 or 3, the upper and lower limits, respectively, of one of the
            following:
            • Off-nominal turns ratio in pu of Winding 3 bus base voltage when |COD3| is
            1 or 2 and CW is 1; RMA3 = 1.1 and RMI3 = 0.9 by default.
            • Actual Winding 3 voltage in kV when |COD3| is 1 or 2 and CW is 2. No default
            is allowed.
            • Off-nominal turns ratio in pu o f nominal Winding 3 voltage (NOMV3) when
            |COD3| is 1 or 2 and CW is 3; RMA3 = 1.1 and RMI3 = 0.9 by default.
            • Phase shift angle in degrees when |COD3| is 3. No default is allowed.
            Not used when |COD3| is 0; RMA3 = 1.1 and RMI3 = 0.9 by default.

        VMA3, VMI3:  When |COD3| is 1, 2 or 3, the upper and lower limits, respectively, of one of the
            following:
            • Voltage at the co ntrolled b us (bus |C ONT3|) in pu when |COD3| is 1.
            VMA3 = 1.1 and VMI3 = 0.9 by default.
            • Reactive power flow into the transformer at the Winding 3 bus end in Mvar
            when |COD3| is 2. No default is allowed.
            • Active power flow into the transformer at the Winding 3 bus end in MW when
            |COD3| is 3. No default is allowed.
            Not used when |COD3| is 0; VMA3 = 1.1 and VMI3 = 0.9 by default.
        NTP3 The number of tap positions available; used when COD3 is 1 or 2. NTP3 must be
            between 2 and 9999. NTP3 = 33 by default.
        TAB3 The number of a transformer impedance correction table if this transformer
            winding’s impedance is to be a function of either off-nominal turns ratio or phase
            shift angle (refer to Transformer Impedance Correction Tables), or 0 if no trans-
            former impedance correction is to be applied to this transformer winding. TAB3 = 0
            by default.
        CR3, CX3 The load drop compensation impedance for voltage controlling transformers
            entered in pu on system base quantities; used when COD3 is 1. CR3 + j CX3 = 0.0
            by default.
        CNXA3 Winding connection angle in degrees; used when COD3 is 5. There are no restrictions
            on the value specified for CNXA3; if it is outside of the range from -90.0 to
            +90.0, CNXA3 is normalized to within this range. CNXA3 = 0.0 by default.

        default.
            Args:
        data:
        version:
        """

        self.windings = 0

        if version == 33:

            # Line 1: for both types
            self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
             self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4, \
             self.VECGRP = data[0]

            # line 2
            if len(data[1]) == 3:
                # 2-windings
                self.windings = 2
                self.R1_2, self.X1_2, self.SBASE1_2 = data[1]
            else:
                # 3-windings
                self.windings = 3
                self.R1_2, self.X1_2, self.SBASE1_2, self.R2_3, self.X2_3, self.SBASE2_3, self.R3_1, \
                 self.X3_1, self.SBASE3_1, self.VMSTAR, self.ANSTAR = data[1]

            # line 3: for both types
            self.WINDV1, self.NOMV1, self.ANG1, self.RATA1, self.RATB1, self.RATC1, self.COD1, self.CONT1, self.RMA1, \
             self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1, self.CNXA1 = data[2]

            # line 4
            if len(data[3]) == 2:
                # 2-windings
                self.WINDV2, self.NOMV2 = data[3]
            else:
                # 3 - windings
                self.WINDV2, self.NOMV2, self.ANG2, self.RATA2, self.RATB2, self.RATC2, self.COD2, self.CONT2, \
                 self.RMA2, self.RMI2, self.VMA2, self.VMI2, self.NTP2, self.TAB2, self.CR2, self.CX2, self.CNXA2, \
                 self.WINDV3, self.NOMV3, self.ANG3, self.RATA3, self.RATB3, self.RATC3, self.COD3, self.CONT3, \
                 self.RMA3, self.RMI3, self.VMA3, self.VMI3, self.NTP3, self.TAB3, \
                 self.CR3, self.CX3, self.CNXA3 = data[3]

        elif version == 32:

            '''
            I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,’NAME’,STAT,O1,F1,...,O4,F4

            R1-2,X1-2,SBASE1-2,R2-3,X2-3,SBASE2-3,R3-1,X3-1,SBASE3-1,VMSTAR,ANSTAR

            WINDV1,NOMV1,ANG1,RATA1,RATB1,RATC1,COD1,CONT1,RMA1,RMI1,VMA1,VMI1,NTP1,TAB1,CR1,CX1,CNXA1

            WINDV2,NOMV2,ANG2,RATA2,RATB2,RATC2,COD2,CONT2,RMA2,RMI2,VMA2,VMI2,NTP2,TAB2,CR2,CX2,CNXA2
            WINDV3,NOMV3,ANG3,RATA3,RATB3,RATC3,COD3,CONT3,RMA3,RMI3,VMA3,VMI3,NTP3,TAB3,CR3,CX3,CNXA3
            '''

            # Line 1: for both types
            if len(data[0]) == 20:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4 = data[0]
            elif len(data[0]) == 18:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2, self.O3, self.F3 = data[0]
            elif len(data[0]) == 16:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2 = data[0]
            elif len(data[0]) == 14:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1 = data[0]
            elif len(data[0]) == 12:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT = data[0]

            # line 2
            if len(data[1]) == 3:
                # 2-windings
                self.windings = 2
                self.R1_2, self.X1_2, self.SBASE1_2 = data[1]
            else:
                # 3-windings
                self.windings = 3
                self.R1_2, self.X1_2, self.SBASE1_2, self.R2_3, self.X2_3, self.SBASE2_3, self.R3_1, \
                 self.X3_1, self.SBASE3_1, self.VMSTAR, self.ANSTAR = data[1]

            # line 3: for both types
            self.WINDV1, self.NOMV1, self.ANG1, self.RATA1, self.RATB1, self.RATC1, self.COD1, self.CONT1, self.RMA1, \
             self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1, self.CNXA1 = data[2]

            # line 4
            if len(data[3]) == 2:
                # 2-windings
                self.WINDV2, self.NOMV2 = data[3]
            else:
                # 3 - windings
                self.WINDV2, self.NOMV2, self.ANG2, self.RATA2, self.RATB2, self.RATC2, self.COD2, self.CONT2, \
                 self.RMA2, self.RMI2, self.VMA2, self.VMI2, self.NTP2, self.TAB2, self.CR2, self.CX2, self.CNXA2, \
                 self.WINDV3, self.NOMV3, self.ANG3, self.RATA3, self.RATB3, self.RATC3, self.COD3, self.CONT3, \
                 self.RMA3, self.RMI3, self.VMA3, self.VMI3, self.NTP3, self.TAB3, \
                 self.CR3, self.CX3, self.CNXA3 = data[3]

        elif version == 30:

            """
            I,J,K,CKT,CW,CZ,CM,MAG1,MAG2,NMETR,'NAME',STAT,Ol,Fl 04,F4

            R1—2,X1—2,SBASE1—2,R2—3,X2—3,SBASE2—3,R3—1,X3—1,SBASE3—1,VMSTAR,ANSTAR

            WINDV1,NOMV1,ANG1, RATA1, BATB1, RATC1, COD1, CONT1, RMA1, RMI1,VMA1,VMI1,NTP1, TAB1, CR1, CX1

            WINDV2 ,NOMV2 , ANG2 , RATA2 , BATB2 , RATC2, COD2, CONT2 , RMA2 , RMI2 , VMA2 , VMI2 ,NTP2, TAB2,CR2, CX2
            WINDV3,NOMV3,ANG3, RATA3, BATB3, RATC3, COD3, CONT3, RMA3, RMI3,VMA3,VMI3,NTP3, TAB3, CR3, CX3
            """

            # Line 1: for both types
            if len(data[0]) == 20:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2, self.O3, self.F3, self.O4, self.F4 = data[0]
            elif len(data[0]) == 18:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2, self.O3, self.F3 = data[0]
            elif len(data[0]) == 16:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1, self.O2, self.F2 = data[0]
            elif len(data[0]) == 14:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT, self.O1, self.F1 = data[0]
            elif len(data[0]) == 12:
                self.I, self.J, self.K, self.CKT, self.CW, self.CZ, self.CM, self.MAG1, self.MAG2, self.NMETR, \
                 self.NAME, self.STAT = data[0]

            # line 2
            if len(data[1]) == 3:
                # 2-windings
                self.windings = 2
                self.R1_2, self.X1_2, self.SBASE1_2 = data[1]
            else:
                # 3-windings
                self.windings = 3
                self.R1_2, self.X1_2, self.SBASE1_2, self.R2_3, self.X2_3, self.SBASE2_3, self.R3_1, \
                self.X3_1, self.SBASE3_1, self.VMSTAR, self.ANSTAR = data[1]

            # line 3: for both types
            self.WINDV1, self.NOMV1, self.ANG1, self.RATA1, self.RATB1, self.RATC1, self.COD1, self.CONT1, self.RMA1, \
            self.RMI1, self.VMA1, self.VMI1, self.NTP1, self.TAB1, self.CR1, self.CX1 = data[2]

            # line 4
            if len(data[3]) == 2:
                # 2-windings
                self.WINDV2, self.NOMV2 = data[3]
            else:
                # 3 - windings
                self.WINDV2, self.NOMV2, self.ANG2, self.RATA2, self.RATB2, self.RATC2, self.COD2, self.CONT2, \
                self.RMA2, self.RMI2, self.VMA2, self.VMI2, self.NTP2, self.TAB2, self.CR2, self.CX2, \
                self.WINDV3, self.NOMV3, self.ANG3, self.RATA3, self.RATB3, self.RATC3, self.COD3, self.CONT3, \
                self.RMA3, self.RMI3, self.VMA3, self.VMI3, self.NTP3, self.TAB3, \
                self.CR3, self.CX3 = data[3]

    def get_object(self, psse_bus_dict):
        """
        Return GridCal branch object
        Args:
            psse_bus_dict: Dictionary that relates PSSe bus indices with GridCal Bus objects

        Returns:
            Gridcal Branch object
        """

        if self.CZ != 1:
            warn('Transformer impedance is not in p.u.')

        if self.windings == 2:
            bus_from = psse_bus_dict[self.I]
            bus_to = psse_bus_dict[self.J]

            r = self.R1_2
            x = self.X1_2
            g = self.MAG1
            b = self.MAG2

            object = Branch(bus_from=bus_from, bus_to=bus_to,
                            name=self.NAME.replace("'", "").strip(),
                            r=r,
                            x=x,
                            g=g,
                            b=b,
                            rate=max(self.RATA1, self.RATB1, self.RATC1),
                            tap=1,
                            shift_angle=0,
                            active=True,
                            mttf=0,
                            mttr=0)
            return [object]

        elif self.windings == 3:

            bus_1 = psse_bus_dict[self.I]
            bus_2 = psse_bus_dict[self.J]
            bus_3 = psse_bus_dict[self.k]

            r = self.R1_2
            x = self.X1_2
            g = self.MAG1
            b = self.MAG2

            object1 = Branch(bus_from=bus_1, bus_to=bus_2,
                             name=self.NAME.replace("'", "").strip() + '_1_2',
                             r=r,
                             x=x,
                             g=g,
                             b=b,
                             rate=max(self.RATA1, self.RATB1, self.RATC1),
                             tap=1,
                             shift_angle=0,
                             active=True,
                             mttf=0,
                             mttr=0)

            r = self.R2_3
            x = self.X2_3
            g = self.MAG1
            b = self.MAG2

            object2 = Branch(bus_from=bus_2, bus_to=bus_3,
                             name=self.NAME.replace("'", "").strip() + '_2_3',
                             r=r,
                             x=x,
                             g=g,
                             b=b,
                             rate=max(self.RATA1, self.RATB1, self.RATC1),
                             tap=1,
                             shift_angle=0,
                             active=True,
                             mttf=0,
                             mttr=0)

            r = self.R3_1
            x = self.X3_1
            g = self.MAG1
            b = self.MAG2

            object3 = Branch(bus_from=bus_3, bus_to=bus_1,
                             name=self.NAME.replace("'", "").strip() + '_3_1',
                             r=r,
                             x=x,
                             g=g,
                             b=b,
                             rate=max(self.RATA1, self.RATB1, self.RATC1),
                             tap=1,
                             shift_angle=0,
                             active=True,
                             mttf=0,
                             mttr=0)

            return [object1, object2, object3]
