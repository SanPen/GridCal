Linear optimal power flow
==========================


General indices and dimensions

.. list-table::
  :widths: 5 20
  :header-rows: 1

  * - Variable
    - Description

  * - n
    - Number of nodes

  * - m
    - Number of branches

  * - ng
    - Number of generators

  * - nb
    - Number of batteries

  * - nl
    - Number of loads

  * - pqpv
    - Vector of node indices of the the PQ and PV buses.

  * - vd
    - Vector of node indices of the the Slack (or VD) buses.


Objective function
------------------

The objective function minimizes the cost of generation plus all the slack variables set in the problem.

.. math::

    min: \quad f = \sum_g cost_g \cdot Pg_g \\
                 + \sum_b cost_b \cdot Pb_b  \\
                 + \sum_l cost_l \cdot LSlack_l \\
                 + \sum_b Fslack1_b + Fslack2_b \\


Power injections
----------------

This equation is not a restriction but the computation of the power injections (fix and LP variables) that
are injected per node, such that the vector :math:`P` is dimensionally coherent with the number of buses.

.. math::

    P = C\_bus\_gen \times Pg  \\
      + C\_bus\_bat \times Pb  \\
      - C\_bus\_load \times (LSlack + Load)


.. list-table::
  :widths: 5 60 25 25 15
  :header-rows: 1

  * - Variable
    - Description
    - Dimensions
    - Type
    - Units

  * - :math:`P`
    - Vector of active power per node.
    - n
    - Float + LP
    - p.u.

  * - :math:`C\_bus\_gen`
    - Bus-Generators connectivity matrix.
    - n,  ng
    - int
    - 1/0

  * - :math:`Pg`
    - Vector of generators active power.
    - ng
    - LP
    - p.u.

  * - :math:`C\_bus\_bat`
    - Bus-Batteries connectivity matrix.
    - nb
    - int
    - 1/0

  * - :math:`Pb`
    - Vector of batteries active power.
    - nb
    - LP
    - p.u.

  * - :math:`C\_bus\_load`
    - Bus-Generators connectivity matrix.
    - n, nl
    - int
    - 1/0

  * - :math:`Load`
    - Vector of active power loads.
    - nl
    - Float
    - p.u.

  * - :math:`LSlack`
    - Vector of active power load slack variables.
    - nl
    - LP
    - p.u.


Nodal power balance
-------------------

These two restrictions are set as hard equality constraints because we want the electrical balance to be fulfilled.

Note that this formulation splits the slack nodes from the non-slack nodes. This is faithful to the original DC
power flow formulation which allows for implicit losses computation.


Equilibrium at the non slack nodes.

.. math::

    B_{pqpv, pqpv} \times \theta_{pqpv} = P_{pqpv}


Equilibrium at the slack nodes.

.. math::

    B_{vd, :} \times \theta = P_{vd}



.. list-table::
  :widths: 5 60 25 25 15
  :header-rows: 1

  * - Variable
    - Description
    - Dimensions
    - Type
    - Units

  * - :math:`B`
    - Matrix of susceptances. Ideally if the imaginary part of Ybus.
    - n, n
    - Float
    - p.u.

  * - :math:`P`
    - Vector of active power per node.
    - n
    - Float + LP
    - p.u.

  * - :math:`\theta`
    - Vector of generators voltage angles.
    - n
    - LP
    - radians.


Branch loading restriction
--------------------------

Something else that we need to do is to check that the branch flows respect the established limits.
Note that because of the linear simplifications, the computed solution in active power might actually be
dangerous for the grid. That is why a real power flow should counter check the OPF solution.

First we compute the arrays of nodal voltage angles for each of the "from" and "to" sides of each branch.
This is not a restriction but a simple calculation to aid the next restrictions that apply per branch.

.. math::

    \theta_{from} = C\_branch\_bus\_{from} \times \theta

    \theta_{to} = C\_branch\_bus\_{to} \times \theta


Now, these are restrictions that define that the "from->to" and the "to->from" flows must respect
the branch rating.

.. math::

    B_{series} \cdot \left( \theta_{from} - \theta_{to} \right) \leq F_{max} + F_{slack1}

    B_{series} \cdot \left( \theta_{to} - \theta_{from} \right) \leq F_{max} + F_{slack2}


Another restriction that we may impose is that the loading slacks must be equal, since they represent the
extra line capacity required to transport the power in both senses of the transportation.

.. math::

    F_{slack1} = F_{slack2}

.. list-table::
  :widths: 5 60 25 25 15
  :header-rows: 1

  * - Variable
    - Description
    - Dimensions
    - Type
    - Units

  * - :math:`B_{series}`
    - Vector of series susceptances of the branches.

      Can be computed as :math:`Im\left(\frac{1}{r + j \cdot x}\right)`
    - m
    - Float
    - p.u.

  * - :math:`C\_branch\_bus_{from}`
    - Branch-Bus connectivity matrix at the "from" end of the branches.
    - m, n
    - int
    - 1/0

  * - :math:`C\_branch\_bus_{to}`
    - Branch-Bus connectivity matrix at the "to" end of the branches.
    - m, n
    - int
    - 1/0

  * - :math:`\theta_{from}`
    - Vector of bus voltage angles at the "from" end of the branches.
    - m
    - LP
    - radians.

  * - :math:`\theta_{to}`
    - Vector of bus voltage angles at the "to" end of the branches.
    - m
    - LP
    - radians.

  * - :math:`\theta`
    - Vector of bus voltage angles.
    - n
    - LP
    - radians.

  * - :math:`F_{max}`
    - Vector of branch ratings.
    - m
    - Float
    - p.u.

  * - :math:`F_{slack1}`
    - Vector of branch rating slacks in the from->to sense.
    - m
    - LP
    - p.u.

  * - :math:`F_{slack2}`
    - Vector of branch rating slacks in the to->from sense.
    - m
    - LP
    - p.u.