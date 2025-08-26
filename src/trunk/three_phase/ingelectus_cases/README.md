# Nombre del Dataset

This is a brief description of the data that is contained in this repository. The repository has two folders:
- cables
- networks

## Cables

### File description

In the 'cables' folder, there are two files that provide access to all the parameterization that has been done for the cables.

- `cablesparameters.json`: contains the 4x4 impedance matrix values in ohm/km
- `cabletypes.csv`: contains a brief description of each cable type here considered

## Networks

### File description

In the 'networks' folder, you can find various subfolders, each containing information about a different Low Voltage network. Within each of them, there are two JSON files that allow the use of each of the networks.

- `imbalance.json`: it contains a scenario of active and reactive power in watts and vars per phase and per load node
- `net.json`: it contains nodes and branches information of the lv network
