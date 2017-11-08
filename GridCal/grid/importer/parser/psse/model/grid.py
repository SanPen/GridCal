from GridCal.grid.model.circuit.multi_circuit import MultiCircuit


class PSSeGrid:

    def __init__(self, data):
        """
        IC
            New Case Flag:
            0 for base case input (i.e., clear the working case before adding data to it)
            1 to add data to the working case
            IC = 0 by default.
        SBASE System MVA base. SBASE = 100.0 by default.
        REV = current revision (32) by default.
        XFRRAT Units of transformer ratings (refer to Transformer Data). The transformer percent
            loading units program option setting (refer to Saved Case Specific Option Settings) is
            set according to this data value.
            XFRRAT < 0 for MVA
            XFRRAT > 0 for current expressed as MVA
            XFRRAT = present transformer percent loading program option setting by default
            (refer to activity OPTN).
        NXFRAT
            Units of ratings of non-transformer branches (refer to Non-Transformer Branch
            Data ). The non-transformer branch percent loading units program option setting
            (refer to Saved Case Specific Option Settings) is set according to this data value.
            NXFRAT < 0 for MVA
            NXFRAT > 0 for current expressed as MVA
            NXFRAT = present non-transformer branch percent loading program option setting
            by default (refer to activity OPTN).
        BASFRQ
            System base frequency in Hertz. The base frequency program option setting (refer to
            Saved Case Specific Option Settings) is set to this data value. BASFRQ = present
            base frequency program option setting value by default (refer to activity OPTN).
        Args:
            data: array with the values
        """

        self.IC, self.SBASE, self.REV, self.XFRRAT, self.NXFRAT, self.BASFRQ = data

        """
        Case Identification Data
        Bus Data
        Load Data
        Fixed Bus Shunt Data
        Generator Data
        Non-Transformer Branch Data
        Transformer Data
        Area Interchange Data
        Two-Terminal DC Transmission Line Data
        Voltage Source Converter (VSC) DC Transmission Line Data
        Transformer Impedance Correction Tables
        Multi-Terminal DC Transmission Line Data
        Multi-Section Line Grouping Data
        Zone Data
        Interarea Transfer Data
        Owner Data
        FACTS Device Data
        Switched Shunt Data
        GNE Device Data
        Induction Machine Data
        Q Record
        """
        self.buses = list()
        self.loads = list()
        self.shunts = list()
        self.generators = list()
        self.branches = list()
        self.transformers = list()

    def get_circuit(self):
        """
        Return GridCal circuit
        Returns:

        """

        circuit = MultiCircuit()
        circuit.Sbase = self.SBASE

        # ---------------------------------------------------------------------
        # Bus related
        # ---------------------------------------------------------------------
        psse_bus_dict = dict()
        for psse_bus in self.buses:

            # relate each PSS bus index with a GridCal bus object
            psse_bus_dict[psse_bus.I] = psse_bus.bus

            # add the bus to the circuit
            circuit.add_bus(psse_bus.bus)

        # Go through loads
        for psse_load in self.loads:

            bus = psse_bus_dict[psse_load.I]
            api_obj = psse_load.get_object(bus)

            circuit.add_load(bus, api_obj)

        # Go through shunts
        for psse_shunt in self.shunts:

            bus = psse_bus_dict[psse_shunt.I]
            api_obj = psse_shunt.get_object(bus)

            circuit.add_shunt(bus, api_obj)

        # Go through generators
        for psse_gen in self.generators:

            bus = psse_bus_dict[psse_gen.I]
            api_obj = psse_gen.get_object()

            circuit.add_controlled_generator(bus, api_obj)

        # ---------------------------------------------------------------------
        # Branches
        # ---------------------------------------------------------------------
        # Go through Branches
        for psse_banch in self.branches:
            # get the object
            branch = psse_banch.get_object(psse_bus_dict)

            # Add to the circuit
            circuit.add_branch(branch)

        # Go through Transformers
        for psse_banch in self.transformers:
            # get the object
            branches = psse_banch.get_object(psse_bus_dict)

            # Add to the circuit
            for branch in branches:
                circuit.add_branch(branch)

        return circuit
