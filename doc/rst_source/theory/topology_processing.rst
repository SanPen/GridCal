
Topology processing
======================

In this section we are going to explain how to do topology processing properly for once and for all.
This is a topic of capital importance in power systems that is rarely dealt with.

A power systems model is a graph. A graph is an abstract construction where relationships are stored.
In power systems, we want to store the relationships between calculation places (buses from now on)
by the means of edges (branches from now on). For the purpose of power systems, both buses and branches have properties
that determine the relationships and even the variation of the relationships with time.

In less abstract terms, the topology processing is to determine the simulatable sub-circuits within a circuit.
In this case a circuit is a collection of equipment, its relationships and states in the most general terms.

From circuit theory we get that:

.. math::

    Y \times V = I

Where Y is the nodal admittance matrix, V is the bus voltages vector and I is the current injections
vector at the buses. To solve for V we need to invert Y:

.. math::

    V = Y^{-1} \times I

The issue here is that Y may not be invertible for any general collection of equipment, hence we need to find the
sub-circuits. Also there may be branches in the circuit with zero-impedance which would make Y singular. We need
to get rid of those as well.

In broad terms the topology process is to:

1. Reduce problematic branches (i.e. switches and jumpers)
2. Find the simulatable islands
3. Segment the circuit in the sub-circuits
4. Simulate each circuit independently *
5. Reassemble the results to match the circuit

Steps 2 ~ 5 are only necessary for those simulations that rely on equality constraints such as the power flow.
Simulations dealing with overdetermined systems like the optimization ones, do not need to handle islands separately.

In performing the topology processing steps, we only need one special function: the islands search.

1 Reducing problematic branches
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Let's consider the following circuit to be processed:

+----------+--------+-----------+-----------+--------+
| Bus from | Bus to | Reducible | impedance | active |
+----------+--------+-----------+-----------+--------+
| 0        | 1      | yes       | 0         | yes    |
+----------+--------+-----------+-----------+--------+
| 0        | 2      | no        | 0.05j     | yes    |
+----------+--------+-----------+-----------+--------+
| 1        | 3      | no        | 0.01j     | yes    |
+----------+--------+-----------+-----------+--------+
| 2        |  3     | yes       | 0         | no     |
+----------+--------+-----------+-----------+--------+

We have 4 buses and 4 branches, 2 of those branches are reducible.
Now we need to construct the adjacency matrix of the reducible branches
with the following algorithm:

.. code-block::

    n = number of buses
    m = number of branches
    A = lil_matrix(n, n)
    for k=0 to m:
        f = bus from of the branch k
        t = bus to of the branch k
        if branch k is active and reducible:
            A(f, f) += 1
            A(f, t) += 1
            A(t, f) += 1
            A(t, t) += 1
        end-if
    end-for

A method that is found to be approximately 2.5 times faster in practice is the following:

.. code-block::

    n = number of buses
    m = number of branches
    C = lil_matrix(m, n)
    for k=0 to m:
        f = bus from of the branch k
        t = bus to of the branch k
        if branch k is active and reducible:
            C(k, f) = 1
            C(k, t) = 1
        end-if
    end-for
    A = C.transpose x C

Obviously C and A in these algorithms must be sparse, otherwise you would need an intractable amount of memory
to compute A for very large grids. This is the case everywhere in power systems.

The nifty trick of composing A with the reducible elements, allows us to use a standard island-finding function
to find which buses are grouped by reducible branches, therefore indicating that all those buses are
"the same bus" for calculation.

In our case, the bus 0 and bus 1 merge into a single one. For practicality we will just indicate that
bus 1 is now the bus 0. The bus 2 and bus 3 remain ungrouped. After processing, the calculation grid should be:

+----------+--------+-----------+
| Bus from | Bus to | impedance |
+----------+--------+-----------+
| 0        | 2      | 0.05j     |
+----------+--------+-----------+
| 0        | 3      | 0.01j     |
+----------+--------+-----------+


2 Finding the simulatable islands
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Now that we have a system without reducible branches, we need to proceed with the cleaning and island slicing.
For that we need to compute the Adjacency matrix, this time using the active branches:

.. code-block::

    n = number of buses
    m = number of branches
    C = lil_matrix(m, n)
    for k=0 to m:
        f = bus from of the branch k
        t = bus to of the branch k
        if (branch k is active) and (bus f is active) and (bus t is active):
            C(k, f) = 1
            C(k, t) = 1
        end-if
    end-for

    A = C.transpose x C

After computing A, we use the standard island-detection function to detect the groups of buses joined by viable
branches. This is, the simulatable islands.

.. code-block::

    islands = find_islands(A)

The islands variable is a list of vectors, each of which contains the indices of the buses of an island.
Now, for every island we need to slice the data, so let's proceed to step 3.


3 Segment the circuit into islands
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We know that and island is a vector of bus indices. So given that we need to slice the grid data structures using
that information. A data structure of buses would be immediately sliceable with the bus indices, but what about
a structure with branch data or a structure with load data?

To be efficient we construct a bus mapping array from the original indices to the island indices. For the
sake of an example let's imagine that we have a circuit with 8 buses and the island we are dealing with has 4 buses
(4, 5, 6, 7).

- We declare an original array of size 8 filled with -1.
- We set the new island indices into the original island positions in that array:

.. code-block::

    island = (4, 5, 6, 7)
    bus_map = -1 x ones(8)
    ii = 0
    for i in island:
        bus_map[i] = ii
        ii += 1
    end-for

    The bus map is:
    bus_map = (-1, -1, -1, -1, 0, 1, 2, 3)

Let's imagine that the grid has the following branch data:

+----------+----------+--------+
| Name     | bus_from | bus_to |
+----------+----------+--------+
| 0:Branch | 2        | 0      |
+----------+----------+--------+
| 1:Branch | 3        | 2      |
+----------+----------+--------+
| 2:Branch | 1        | 0      |
+----------+----------+--------+
| 3:Branch | 1        | 2      |
+----------+----------+--------+
| 4:Branch | 6        | 4      |
+----------+----------+--------+
| 5:Branch | 7        | 6      |
+----------+----------+--------+
| 6:Branch | 5        | 4      |
+----------+----------+--------+
| 7:Branch | 5        | 6      |
+----------+----------+--------+

With a simple algorithm we can determine which branch indices belong to the island:

.. code-block::

    m = number of branches
    elements_indices = list()
    for k=0 to m:
        f = branch k from bus
        t = branch k to bus
        if bus_map[f] > -1 and bus_map[t] > -1:
            elements_indices.add(k)

    in this case
    elements_indices = (4, 5, 6, 7)

Hence, the sliced island branch data is:

+----------+----------+--------+
| Name     | bus_from | bus_to |
+----------+----------+--------+
| 4:Branch | 6        | 4      |
+----------+----------+--------+
| 5:Branch | 7        | 6      |
+----------+----------+--------+
| 6:Branch | 5        | 4      |
+----------+----------+--------+
| 7:Branch | 5        | 6      |
+----------+----------+--------+

Using the bus_map, we need to re-map the "from" and "to" buses of the sliced structure:

+----------+----------+--------+
| Name     | bus_from | bus_to |
+----------+----------+--------+
| 4:Branch | 2        | 0      |
+----------+----------+--------+
| 5:Branch | 3        | 2      |
+----------+----------+--------+
| 6:Branch | 1        | 0      |
+----------+----------+--------+
| 7:Branch | 1        | 2      |
+----------+----------+--------+

For a structure like loads would be exactly the same but using only one bus index instead of "from" and "to".

The collection of sliced structures becomes a new circuit that we can effectively use in numerical calculations like
power flows. In practice this step has far more value that what one may anticipate since it cleans the grid of
any inactive buses, branches or devices that would pollute our simulation without noticing, causing errors.

Islands search function
^^^^^^^^^^^^^^^^^^^^^^^^^

The island search function is a depth-first search that exploits the CSC structure of the adjacency matrix.
The particular version of the DFS algorithm presented here avoids recursivity in favor of cues for faster execution.

.. code-block::

    indptr: index pointers in the CSC scheme
    indices: column indices in the CSCS scheme
    active: array of bus active states
    n = bus number

    visited = zeros(n)

    islands = list()

    node_count = 0
    current_island = zeros(n)

    island_idx = 0

    for node=0 to node_number:

        if not visited[node] and active[node]:

            stack = list()
            stack.add(node)

            while stack.size > 0:

                v = stack.first
                remove first element from the stack

                if not visited[v]:

                    visited[v] = 1

                    current_island[node_count] = v
                    node_count += 1

                    for i=indptr[v] to indptr[v + 1]:
                        k = indices[i]
                        if not visited[k] and active[k]:
                            stack.add(k)
                        end-if
                    end-for
                end-if
            end-while

            # slice the current island to its actual size
            island = current_island[:node_count].copy()
            island.sort()  # sort in-place

            # assign the current island
            islands.append(island)

            # increase the islands index, because
            island_idx += 1

            # reset the current island
            # no need to re-allocate "current_island" since it is going to be overwritten
            node_count = 0
        end-if
    end-for


The spirit of CIM
^^^^^^^^^^^^^^^^^^

If you have read anything about CIM or CGMES, or you have been in the guild discussions,
you most definitely have heard about node-breaker and bus-branch modelling styles as two different things.
Throughout the years the introductory training course of CGMEs given by ENTSO-e teaches that you can either model
with connectivity nodes or with buses. This has been taught to hundreds of engineers used to model with
buses, lines, etc. that suddenly experience a vast complexity increase.
However, this complexity is unjustified since the node-breaker / bus-branch philosophies are the same.
We have inadvertently seen so in this section. Allow me to elaborate;

The bus-branch modelling: This is a style of modelling where you model using TopologicalNodes.
The node-breaker modelling: This is a style of modelling where you model using ConnectivityNodes.

There is the common assumption that the bus-branch models do not have
switches, while the node-breaker modes do have them. In practice both are possible, but allow me to go even further;
A ConnectivityNode can have a 1:1 association with a TopologyNode, meaning that any ConnectivityNOde is in the end
a TopologyNode. So, where is the difference? There is no difference. Both styles are the same.

The original spirit of CIM is to model the grid using ConnectivityNodes and the TopologyNodes arise as a side effect
after performing the topological reduction (reducing the problematic branches). Is the TopologicalNode strictly needed?
Absolutely not. The practice has derived in exchanging both sets; the after-processing data as node-breaker and the
post-processed data as bus-branch. However this is just an artificial complication.
This has proven to be extremely problematic in practice.

So, in the spirit of CIM, the ConnectivityNodes are indeed the old fashioned Buses.

How is it done in GridCal?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In GridCal we have the MultiCircuit as the grid in-memory database. No topological processing should ever be done
over the database since there is a risk of changing the elements topology with respect to the previous definition. i.e
I might have a generator connected to Bus1, but after topology processing is connected to Bus2.
How can I recover that originally it was connected to Bus1? I cannot. So, where do we perform the topology processing?

Luckily, we have the NumericalCircuit. This is a snapshot of the MultiCircuit at some time index.
This snapshot is fungible, meaning that any changes to it will not affect the MultiCircuit and
will disappear after calculation. So, we perform the topology processing steps at the NumericalCircuit as
explained at the beginning of this section.

With regards to CIM compatibility, we have made only one change: All ConnectivityNodes must create a bus
or have an existing bus associated. Likewise, all BusBars must create connectivity node or have one associated.
This ensures, that whatever object you use for modelling, in the end you end up using a bus, ensuring consistency
in all calculation processes.

