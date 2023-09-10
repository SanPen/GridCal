# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


class TapChanger:
    """
    The **TapChanger** class defines a transformer's tap changer, either onload or
    offload. It needs to be attached to a predefined transformer (i.e. a
    :ref:`Branch<branch>` object).

    The following example shows how to attach a tap changer to a transformer tied to a
    voltage regulated :ref:`bus`:

    .. code:: ipython3

        from GridCalEngine.Core.multi_circuit import MultiCircuit
        from GridCalEngine.Core.Devices import *
        from GridCalEngine.device_types import *

        # Create grid
        grid = MultiCircuit()

        # Create buses
        POI = Bus(name="POI",
                  vnom=100, #kV
                  is_slack=True)
        grid.add_bus(POI)

        B_C3 = Bus(name="B_C3",
                   vnom=10) #kV
        grid.add_bus(B_C3)

        # Create transformer types
        SS = TransformerType(name="SS",
                             hv_nominal_voltage=100, # kV
                             lv_nominal_voltage=10, # kV
                             nominal_power=100, # MVA
                             copper_losses=10000, # kW
                             iron_losses=125, # kW
                             no_load_current=0.5, # %
                             short_circuit_voltage=8) # %
        grid.add_transformer_type(SS)

        # Create transformer
        X_C3 = Branch(bus_from=POI,
                      bus_to=B_C3,
                      name="X_C3",
                      branch_type=BranchType.Transformer,
                      template=SS,
                      bus_to_regulated=True,
                      vset=1.05)

        # Attach tap changer
        X_C3.tap_changer = TapChanger(taps_up=16, taps_down=16, max_reg=1.1, min_reg=0.9)
        X_C3.tap_changer.set_tap(X_C3.tap_module)

        # Add transformer to grid
        grid.add_branch(X_C3)

    Arguments:

        **taps_up** (int, 5): Number of taps position up

        **taps_down** (int, 5): Number of tap positions down

        **max_reg** (float, 1.1): Maximum regulation up i.e 1.1 -> +10%

        **min_reg** (float, 0.9): Maximum regulation down i.e 0.9 -> -10%

    Additional Properties:

        **tap** (int, 0): Current tap position

    """

    def __init__(self, taps_up=5, taps_down=5, max_reg=1.1, min_reg=0.9):
        self.max_tap = taps_up

        self.min_tap = -taps_down

        self.inc_reg_up = (max_reg - 1.0) / taps_up

        self.inc_reg_down = (1.0 - min_reg) / taps_down

        self.tap = 0

    def tap_up(self):
        """
        Go to the next upper tap position
        """
        if self.tap + 1 <= self.max_tap:
            self.tap += 1

    def tap_down(self):
        """
        Go to the next upper tap position
        """
        if self.tap - 1 >= self.min_tap:
            self.tap -= 1

    def get_tap(self):
        """
        Get the tap voltage regulation module
        """
        if self.tap == 0:
            return 1.0
        elif self.tap > 0:
            return 1.0 + self.tap * self.inc_reg_up
        elif self.tap < 0:
            return 1.0 + self.tap * self.inc_reg_down

    def set_tap(self, tap_module):
        """
        Set the integer tap position corresponding to a tap value

        Attribute:

            **tap_module** (float): Tap module centered around 1.0

        """
        if tap_module == 1.0:
            self.tap = 0
        elif tap_module > 1:
            self.tap = round((tap_module - 1.0) / self.inc_reg_up)
        elif tap_module < 1:
            self.tap = -round((1.0 - tap_module) / self.inc_reg_down)