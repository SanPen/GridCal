from GridCal.Engine.Devices.branch import Branch
from GridCal.Engine.Devices.bus import Bus
from GridCal.Engine.Devices.generator import Generator
from GridCal.Engine.Devices.load import Load
from GridCal.Engine.Devices.types import BranchType
from GridCal.Engine.Core.multi_circuit import MultiCircuit


def get_grid_lynn_5_bus_wiki():
    grid = MultiCircuit(name='lynn 5 bus')
    bus1 = Bus(
        name='Bus1',
        vnom=10,  # Nominal voltage in kV
        vmin=0.9,  # Bus minimum voltage in per unit
        vmax=1.1,  # Bus maximum voltage in per unit
        xpos=0,  # Bus x position in pixels
        ypos=0,  # Bus y position in pixels
        height=0,  # Bus height in pixels
        width=0,  # Bus width in pixels
        active=True,  # Is the bus active?
        is_slack=False,  # Is this bus a slack bus?
        area='Default',  # Area (for grouping purposes only)
        zone='Default',  # Zone (for grouping purposes only)
        substation='Default'  # Substation (for grouping purposes only)
    )
    bus2 = Bus(name='Bus2')
    bus3 = Bus(name='Bus3')
    bus4 = Bus(name='Bus4')
    bus5 = Bus(name='Bus5')
    grid.add_bus(bus1)
    grid.add_bus(bus2)
    grid.add_bus(bus3)
    grid.add_bus(bus4)
    grid.add_bus(bus5)
    l2 = Load(
        name='Load',
        # impedance=complex(0, 0),
        # Impedance of the ZIP model in MVA at the nominal voltage
        # current=complex(0, 0),
        # Current of the ZIP model in MVA at the nominal voltage
        # power=complex(40, 20),  # Power of the ZIP model in MVA
        # impedance_prof=None,  # Impedance profile
        # current_prof=None,  # Current profile
        # power_prof=None,  # Power profile
        active=True,  # Is active?
        mttf=0.0,  # Mean time to failure
        mttr=0.0  # Mean time to recovery
    )
    grid.add_load(bus2, l2)
    grid.add_load(bus3, Load(
        # power=complex(25, 15)
    ))
    grid.add_load(bus4, Load(
        # power=complex(40, 20)
    ))
    grid.add_load(bus5, Load(
        # power=complex(50, 20)
    ))
    g1 = Generator(
        name='gen',
        active_power=0.0,
        # Active power in MW, since this generator is used to set the slack , is 0
        voltage_module=1.0,  # Voltage set point to control
        Qmin=-9999,  # minimum reactive power in MVAr
        Qmax=9999,  # Maximum reactive power in MVAr
        Snom=9999,  # Nominal power in MVA
        power_prof=None,  # power profile
        vset_prof=None,  # voltage set point profile
        active=True  # Is active?
    )
    grid.add_generator(bus1, g1)
    branch_1 = Branch(
        bus_from=bus1,
        bus_to=bus2,
        name='Line 1-2',
        r=0.05,  # resistance of the pi model in per unit
        x=0.11,  # reactance of the pi model in per unit
        g=1e-20,  # conductance of the pi model in per unit
        b=0.02,  # susceptance of the pi model in per unit
        rate=50,  # Rate in MVA
        tap=1.0,  # Tap value (value close to 1)
        shift_angle=0,  # Tap angle in radians
        active=True,  # is the branch active?
        mttf=0,  # Mean time to failure
        mttr=0,  # Mean time to recovery
        branch_type=BranchType.Line,  # Branch type tag
        length=1,  # Length in km (to be used with templates)
        # type_obj=BranchTemplate()
        # Branch template (The default one is void)
    )
    grid.add_branch(branch_1)
    grid.add_branch(
        Branch(bus1, bus3, name='Line 1-3', r=0.05, x=0.11, b=0.02, rate=50))
    grid.add_branch(
        Branch(bus1, bus5, name='Line 1-5', r=0.03, x=0.08, b=0.02, rate=80))
    grid.add_branch(
        Branch(bus2, bus3, name='Line 2-3', r=0.04, x=0.09, b=0.02, rate=3))
    grid.add_branch(
        Branch(bus2, bus5, name='Line 2-5', r=0.04, x=0.09, b=0.02, rate=10))
    grid.add_branch(
        Branch(bus3, bus4, name='Line 3-4', r=0.06, x=0.13, b=0.03, rate=30))
    grid.add_branch(
        Branch(bus4, bus5, name='Line 4-5', r=0.04, x=0.09, b=0.02, rate=30))

    grid.compile()

    return grid
