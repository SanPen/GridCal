import GridCalEngine.Core.Devices as dev
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
def createGrid():
    """
    Función para crear un Multicircuit a partir de la red del diagrama 1
    """

    grid = MultiCircuit()

    # Añadir busbar
    for i in range(5):
        b = dev.BusBar(name='B{}'.format(i+1))
        grid.bus_bars.append(b)
    # Añadir CN
    for i in range(16):
        t = dev.ConnectivityNode(name='T{}'.format(i+1))
        grid.connectivity_nodes.append(t)
        # Indicar al CN cuál es su busbar
    # Añadir líneas

    # Añadir los switches


def topology_proc(grid: MultiCircuit):

    # Usar código switch_reduction_sparse

    ## Crear matrices de conectividad a partir de MultiCircuit. Replicar
    grid.get_branches() # Devuelve una lista de todas las ramas en el orden de cálculo