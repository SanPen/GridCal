from GridCal.Engine.Devices import *

test_name = "test_cable_temp"

def test_cable_temp():
    """
    Very simple test to validate the effect of cable temperature on a cable's
    resistance.
    """

    # Create buses
    B_C3 = Bus(name="B_C3",
               vnom=10) #kV

    B_MV_M32 = Bus(name="B_MV_M32",
                   vnom=10) #kV

    cable = Branch(bus_from=B_C3,
                   bus_to=B_MV_M32,
                   name="C_M32",
                   r=0.784,
                   x=0.174,
                   Tb=20, # °C
                   Tc=90, # °C
                   k=ThermalConstant.Copper)

    assert round(cable.R, 4) == 0.9613
