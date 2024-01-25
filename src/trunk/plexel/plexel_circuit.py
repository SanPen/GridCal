from typing import List
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit



class PlexelObject:

    def __init__(self):
        pass


class PlexelCircuit:

    def __str__(self):

        self.objects: List[PlexelObject] = list()
        self.memberships = list()
        self.categories = list()
        self.attributes = list()
        self.properties = list()

    def convert(self, grid: MultiCircuit):
        pass

    def save(self, fname: str):
        pass


if __name__ == "__main__":
    import os
    import GridCalEngine.api as gce

    # fname = os.path.join("..", "..", "..", "Grids_and_profiles/grids/hydro_IEEE39_2.gridcal")
    fname = os.path.join("..", "..", "..", "Grids_and_profiles/grids/IEEE 14 bus.raw")

    my_grid = gce.open_file(fname)

    my_plexel_circuit = PlexelCircuit()

    my_plexel_circuit.convert(my_grid)
