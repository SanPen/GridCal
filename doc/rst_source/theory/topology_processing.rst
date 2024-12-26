
Topology processing
########################

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

    Y \times V = I^*

Where Y is the nodal admittance matrix, V is the bus voltages vector and I is the current injections
vector at the buses. To solve for V we need to invert Y:

.. math::

    V = Y^{-1} \times I^*

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
Simulations that create overdetermined linear systems like the optimization ones,
do not need to handle islands separately.

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

Ofcourse, each island must have a voltage source (i.e. a slack node)
otherwise there is no way the island is powered and it will be in blackout.

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

If you've encountered CIM or CGMES, or participated in guild discussions, you've likely heard about **node-breaker**
and **bus-branch** modeling styles as distinct approaches. ENTSO-e's introductory CGMES training has historically
taught that you can model using either **connectivity nodes** or **buses**. This guidance has been shared with
hundreds of engineers accustomed to simpler models of buses, lines, etc. only to face a what seems to be
gratuitous complexity.

After deep examination one finds that this complexity is indeed unjustified.
The **node-breaker** and **bus-branch** philosophies are fundamentally
the same, as we have experimented in the described processes.
The modelling approaches are often thought of as:

- **Bus-branch modeling**: This style involves using **TopologicalNodes** and no switches.
- **Node-breaker modeling**: This style involves using **ConnectivityNodes** and switches.

A common misconception is that bus-branch models lack switches, whereas node-breaker models include them. In
practice, both approaches can incorporate switches. That fact is often discoursed at the official CGMES trainings.
But, if a **ConnectivityNode** can have a 1:1 association with a **TopologicalNode**,
this involves that any ConnectivityNode ultimately represents a TopologicalNode.
So, what’s the difference? **There is no difference. Both styles are fundamentally the same.**

CIM’s design philosophy is to model grids using **ConnectivityNodes**, with **TopologicalNodes** emerging
naturally through topological reductions (e.g., simplifying branches). The need for TopologicalNodes is purely
situational and not fundamental. Over time, the practice of treating detailed models as node-breaker models
and processed less detailed models as bus-branch has created an artificial divide that has proven
impractical and needlessly complicated. One can understand that the lack of a properly clear topology processing
has probably sparked this complexity as some sort of middle ground that ends up being the worst of both  approaches.

If we examine the original spirit of CIM: **ConnectivityNodes are no different from traditional Buses.**
The distinction is a myth that adds unnecessary complexity to modeling workflows.


How is it done in GridCal?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In GridCal, the **MultiCircuit** serves as the grid's in-memory database. It is crucial that no topological processing
is ever performed directly on the MultiCircuit. Doing so risks altering the topology of elements, potentially breaking
the consistency of the original configuration.

For example, imagine a generator initially connected to **Bus 1**. After performing topological processing, it might
end up connected to **Bus 2**. How could we recover the original connection to **Bus 1**? Simply put, we cannot.

If topology processing should not occur over the database, then where should it be done?

Fortunately, GridCal provides the **NumericalCircuit**, a snapshot of the MultiCircuit at a specific state. This
snapshot is **fungible**, meaning any modifications made to it will not impact the original MultiCircuit and will
vanish after the calculation. As such, all topology processing steps are performed on the **NumericalCircuit**, as
described earlier in this section.

**CIM Compatibility Adjustments**

To ensure compatibility with CIM standards, we have introduced a single adjustment:

- Every **ConnectivityNode** must either create a bus or be associated with an existing bus.
- Similarly, every **BusBar** must either create a connectivity node or be associated with one.

This guarantees that no matter which object you use for modeling, the system will ultimately rely on buses,
maintaining consistency across all calculation processes.


