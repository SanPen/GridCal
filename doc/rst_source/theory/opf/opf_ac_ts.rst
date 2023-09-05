AC Linear optimal power flow time series
========================================

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

  * - nt
    - Number of time steps

  * - pqpv
    - Vector of node indices of the the PQ and PV buses.

  * - vd
    - Vector of node indices of the the Slack (or VD) buses.


Objective function
------------------

The objective function minimizes the cost of generation plus all the slack variables set in the problem.

.. math::

    min: \quad f = \sum_t^{nt}  \sum_g^{ng} cost_g \cdot Pg_{g,t} \\
                 + \sum_t^{nt}  \sum_b^{nb} cost_b \cdot Pb_{b, t}  \\
                 + \sum_t^{nt}  \sum_l^{nl} cost_l \cdot LSlack_{l, t} \\
                 + \sum_t^{nt}  \sum_i^{m} Fslack1_{i,t} + Fslack2_{i,t} \\


Power injections
----------------

This equation is not a restriction but the computation of the power injections (fix and LP variables) that
are injected per node, such that the vector :math:`P` is dimensionally coherent with the number of buses.

.. math::

    P = - C\_bus\_load \times (LSlack + P_{load}) \\
        + C\_bus\_gen \times Pg  \\
        + C\_bus\_bat \times Pb


.. math::

    Q = - C\_bus\_load \times (LSlack + Q_{load})


.. list-table::
  :widths: 5 60 25 25 15
  :header-rows: 1

  * - Variable
    - Description
    - Dimensions
    - Type
    - Units

  * - :math:`P`
    - Matrix of active power per node and time step.
    - n, nt
    - Float + LP
    - p.u.

  * - :math:`C\_bus\_gen`
    - Bus-Generators connectivity matrix.
    - n,  ng
    - int
    - 1/0

  * - :math:`Pg`
    - Matrix of generators active power per time step.
    - ng, nt
    - LP
    - p.u.

  * - :math:`C\_bus\_bat`
    - Bus-Batteries connectivity matrix.
    - nb
    - int
    - 1/0

  * - :math:`Pb`
    - Matrix of batteries active power per time step.
    - nb, nt
    - LP
    - p.u.

  * - :math:`C\_bus\_load`
    - Bus-Generators connectivity matrix.
    - n, nl
    - int
    - 1/0

  * - :math:`P_{load}`
    - Matrix of active power loads per time step.
    - nl, nt
    - Float
    - p.u.

  * - :math:`Q_{load}`
    - Matrix of reactive power loads per time step.
    - nl, nt
    - Float
    - p.u.

  * - :math:`LSlack`
    - Matrix of active power load slack variables per time step.
    - nl, nt
    - LP
    - p.u.


Nodal power balance
-------------------


This is the OPF based on the formulation presented in *Linearized AC Load Flow Applied to Analysis*
*in Electric Power Systems* [1]_, we obtain a way to solve circuits in one shot
(without iterations) and with quite positive results for a linear approximation.

.. math::

    \begin{bmatrix}
    -Bs_{pqpv, pqpv} & G_{pqpv, pq} \\
    -Gs_{pq, pqpv} & -B_{pq,pq} \\
    \end{bmatrix}
    \times
    \begin{bmatrix}
    \Delta \theta_{pqpv}\\
    \Delta Vm_{pq}\\
    \end{bmatrix}
    =
    \begin{bmatrix}
    P_{pqpv}\\
    Q_{pq}\\
    \end{bmatrix}

This matrix equation turns into two sets of restrictions:

.. math::

    -Bs_{pqpv, pqpv} \times  \Delta \theta_{pqpv} +  G_{pqpv, pq} \times \Delta Vm_{pq} = P_{pqpv}

.. math::

    -Gs_{pq, pqpv} \times \Delta \theta_{pqpv} - B_{pq,pq} \times \Delta Vm_{pq} = Q_{pq}

An additional set of restrictions is needed in order to include the slack nodes in the formulation. These are
not required for the power flow formulation but they are in the optimal power flow one that is presented.

.. math::

    -Bs_{vd, :} \times  \Delta \theta +  G_{vd, :} \times \Delta Vm = P_{vd}

Remember to set the slack-node voltage angles and module increments
and the PV node voltage module increments to zero!
Otherwise the generator's power will no be used by the solver to provide voltage values.

.. math::

    \Delta\theta_{(vd, :)} = 0


.. math::

    \Delta Vm_{(vdpv, :)} = 0


.. list-table::
  :widths: 5 60 25 25 15
  :header-rows: 1

  * - Variable
    - Description
    - Dimensions
    - Type
    - Units

  * - :math:`B`
    - Matrix of susceptances. :math:`Im\{Y\}`.
    - n, n
    - Float
    - p.u.

  * - :math:`Bs`
    - Matrix of susceptances of the series elements. :math:`Im \left\{Y_{series} \right\}`.
    - n, n
    - Float
    - p.u.

  * - :math:`G`
    - Matrix of conductances. :math:`Re\{Y\}`.
    - n, n
    - Float
    - p.u.

  * - :math:`Gs`
    - Matrix of conductances of the series elements. :math:`Re \left\{Y_{series} \right\}`.
    - n, n
    - Float
    - p.u.

  * - :math:`P`
    - Matrix of active power per node and per time step.
    - n, nt
    - Float + LP
    - p.u.

  * - :math:`Q`
    - Matrix of reactive power per node and per time step.
    - n, nt
    - Float + LP
    - p.u.

  * - :math:`\Delta \theta`
    - Matrix of generators voltage angles increment per node and per time step.
    - n, nt
    - LP
    - radians.

  * - :math:`\Delta Vm`
    - Matrix of generators voltage module increments per node and per time step.
    - n, nt
    - LP
    - p.u.


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
    - Matrix of bus voltage angles at the "from" end of the branches per bus and time step.
    - m, nt
    - LP
    - radians.

  * - :math:`\theta_{to}`
    - Matrix of bus voltage angles at the "to" end of the branches per bus and time step.
    - m, nt
    - LP
    - radians.

  * - :math:`\theta`
    - Matrix of bus voltage angles per bus and time step.
    - n, nt
    - LP
    - radians.

  * - :math:`F_{max}`
    - Matrix of branch ratings per branch and time step.
    - m, nt
    - Float
    - p.u.

  * - :math:`F_{slack1}`
    - Matrix of branch rating slacks in the from->to sense per branch and time step.
    - m, nt
    - LP
    - p.u.

  * - :math:`F_{slack2}`
    - Matrix of branch rating slacks in the to->from sense per branch and time step.
    - m, nt
    - LP
    - p.u.


Battery discharge restrictions
------------------------------

The first value of the batteries' energy is the initial state of charge (:math:`SoC_0`) times the battery capacity.

.. math::

    E_0 = SoC_0 \cdot Capacity


The capacity in the subsequent time steps is the previous capacity minus the power dispatched.
Note that the convention is that the positive power is discharged by the battery and the negative power
values represent the power charged by the battery.

.. math::

    E_t = E_{t-1} - \frac{\Delta_t \cdot Pb}{Efficiency} \quad \quad \forall t \in \{ 1, nt-1 \}


The batteries' energy has to be kept within the batteries' operative ranges.

.. math::

    SoC_{min} \cdot Capacity \leq E_t \leq SoC_{max} \cdot Capacity \quad \forall t \in \{ 0, nt-1 \}


.. list-table::
  :widths: 5 60 25 25 15
  :header-rows: 1

  * - Variable
    - Description
    - Dimensions
    - Type
    - Units

  * - :math:`E`
    - Matrix of energy stored in the batteries.
    - nb, nt
    - LP
    - p.u.

  * - :math:`SoC_0`
    - Vector of initial states of charge.
    - nb
    - Float
    - p.u.

  * - :math:`SoC_{max}`
    - Vector of maximum states of charge.
    - nb
    - Float
    - p.u.

  * - :math:`SoC_{min}`
    - Vector of minimum states of charge.
    - nb
    - Float
    - p.u.

  * - :math:`Capacity`
    - Vector of battery capacities.
    - nb
    - Float
    - h :math:`\left(\frac{MWh}{MW \quad base} \right)`

  * - :math:`\Delta_t`
    - Time increment in the interval [t-1, t].
    - 1
    - Float
    - h.

  * - :math:`Pb`
    - Vector of battery power injections.
    - nb
    - LP
    - p.u.

  * - :math:`Efficiency`
    - Vector of Battery efficiency for charge and discharge.
    - nb
    - Float
    - p.u.


.. [1] Rossoni, P. / Moreti da Rosa, W. / Antonio Belati, E., Linearized AC Load Flow
    Applied to Analysis in Electric Power Systems, IEEE Latin America Transactions,
    14, 9; 4048-4053, 2016