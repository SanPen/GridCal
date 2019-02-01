.. _linear_ac_power_flow:

Linear AC Power Flow
====================

Following the formulation presented in [1]_, we obtain a way to solve circuits in one shot (without iterations) and quite positive results for a linear approximation.

.. math::

    \begin{bmatrix}
    A_{11} & A_{12} \\
    A_{21} & A_{22} \\
    \end{bmatrix}
    \times
    \begin{bmatrix}
    \Delta \theta\\
    \Delta |V|\\
    \end{bmatrix}
    =
    \begin{bmatrix}
    Rhs_1\\
    Rhs_2\\
    \end{bmatrix}

Where:

- :math:`A_{11} = -Im\left(Y_{series}[pqpv, pqpv]\right)`
- :math:`A_{12} = Re\left(Y_{bus}[pqpv, pq]\right)`
- :math:`A_{21} = -Im\left(Y_{series}[pq, pqpv]\right)`
- :math:`A_{22} = -Re\left(Y_{bus}[pq, pq]\right)`
- :math:`Rhs_1 = P[pqpv]`
- :math:`Rhs_2 = Q[pq]`

Here, :math:`Y_{bus}` is the normal circuit admittance matrix and :math:`Y_{series}`
is the admittance matrix formed with only series elements of the :math:`\pi` model,
this is neglecting all the shunt admittances.

Solving the vector :math:`[\Delta \theta + 0, \Delta |V| + 1]` we get :math:`\theta`
for the pq and pv nodes and :math:`|V|` for the pq nodes.

For equivalence with the paper:

- :math:`-B' = -Im(Y_{series}[pqpv, pqpv])`
- :math:`G = Re(Y_{bus}[pqpv, pq])`
- :math:`-G' = -Im(Y_{series}[pq, pqpv])`
- :math:`-B = -Re(Y_{bus}[pq, pq])`

.. [1] Rossoni, P. / Moreti da Rosa, W. / Antonio Belati, E., Linearized AC Load Flow
    Applied to Analysis in Electric Power Systems, IEEE Latin America Transactions,
    14, 9; 4048-4053, 2016
