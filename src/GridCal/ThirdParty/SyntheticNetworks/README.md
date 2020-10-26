Welcome to SyntheticNetworks' documentation!
============================================

This work is based on the network creation algorithm published in:

[1] A Random Growth Model for Power Grids and Other Spatially Embedded Infrastructure Networks
Paul Schultz, Jobst Heitzig, and Juergen Kurths
Eur. Phys. J. Special Topics on "Resilient power grids and extreme events" (2014)
DOI: 10.1140/epjst/e2014-02279-6

There you can find a detailed description of the algorithm.

Adaptation to multilayer networks is a work in progress. You can 
find a first report here:

[2] A Network of Networks Approach to Interconnected Power Grids
Paul Schultz, Frank Hellmann, Jobst Heitzig, and Juergen Kurths
arXiv:1701.06968 [physics.soc-ph]

The single-node basin stability predictor has appeared here:

[3] Detours around basin stability in power networks
Paul Schultz, Jobst Heitzig, and Juergen Kurths
New J. Phys. 16, 125001 (2014).
DOI: 10.1088/1367-2630/16/12/125001

## Usage Example

```python
# create container for a random powergrid graph
g = RPG()
# activate detailed output
g.debug = True 
# set growth parameters
# default values: n = 20, n0 = 10, p = 0.2, q = 0.3, r = 1. / 3., s = 0.1
g.set_params(n=100, n0=1, r=1./3.) 
# initialize the network with a minimum spanning tree of size n0
g.initialise() 
# perform growth steps until the network has size n
g.grow() 

print g

print g.stats

g.save_graph()

g.plot_net()
```

![(Adapted from [1]) Polar examples of random grid topologies with N=400 nodes
and degree distributions for N=4000 nodes, generated with our model (s=0 in all plots).
Links added in step I2, I3, G2, G3, or G4 are plotted in black, brown, blue, red,
or orange, respectively. Left column: whole grid constructed with minimum spanning tree in
initial phase (N 0 = N ); Middle and right columns: no initial phase, whole grid successively
grown (N0 = 1, middle: p > 0, q = 0; right: p = 0, q > 0). Top row: tree-shaped grids
with mean degree approx. 2 (p = q = 0); Middle row: grids with redundant links minimizing
spatial distance (p + q = 1, r = 0); Bottom row: grids with redundant links maximizing a
redundancy/cost trade-off (r = 1). Top right: Detail of real-world power grid in ENTSO-E
region 1 (mainland Europe) for comparison.](net_exp.png)
*(Adapted from [1]) Polar examples of random grid topologies with N=400 nodes
and degree distributions for N=4000 nodes, generated with our model (s=0 in all plots).
Links added in step I2, I3, G2, G3, or G4 are plotted in black, brown, blue, red,
or orange, respectively. Left column: whole grid constructed with minimum spanning tree in
initial phase (N 0 = N ); Middle and right columns: no initial phase, whole grid successively
grown (N0 = 1, middle: p > 0, q = 0; right: p = 0, q > 0). Top row: tree-shaped grids
with mean degree approx. 2 (p = q = 0); Middle row: grids with redundant links minimizing
spatial distance (p + q = 1, r = 0); Bottom row: grids with redundant links maximizing a
redundancy/cost trade-off (r = 1). Top right: Detail of real-world power grid in ENTSO-E
region 1 (mainland Europe) for comparison.*

