.. _linear_ac_power_flow:

Linear AC Power Flow
====================

Following the formulation presented in *Linearized AC Load Flow Applied to Analysis*
*in Electric Power Systems* [1]_, we obtain a way to solve circuits in one shot
(without iterations) and with quite positive results for a linear approximation.

.. math::

    \begin{bmatrix}
    -Bs_{pqpv, pqpv} & G_{pqpv, pq} \\
    -Gs_{pq, pqpv} & -B_{pq, pq} \\
    \end{bmatrix}
    \times
    \begin{bmatrix}
    \Delta \theta_{pqpv}  \\
    \Delta |V|_{pq}\\
    \end{bmatrix}
    =
    \begin{bmatrix}
    P_{pqpv}\\
    Q_{pq}\\
    \end{bmatrix}

Where:

- :math:`G = Re\left(Y_{bus}\right)`
- :math:`B = Re\left(Y_{bus}\right)`
- :math:`Gs = Im\left(Y_{series}\right)`
- :math:`Bs = Im\left(Y_{series}\right)`


Here, :math:`Y_{bus}` is the normal circuit admittance matrix and :math:`Y_{series}`
is the admittance matrix formed with only series elements of the :math:`\pi` model,
this is neglecting all the shunt admittances.


After the voltage delta computations, we obtain the final voltage vector by:

- Copy the initial voltage: :math:`V = V_0`. This copies the slack values.

- Set the voltage module values for the pq nodes: :math:`|V|_{pq} = 1 - \Delta |V|_{pq}`

- Copy the voltage module values for the pq nodes: :math:`|V|_{pv} = |V_0|_{pv}`

- Set the voltage angle for the pq and pv nodes: :math:`\theta_{pqpv} = \Delta \theta_{pqpv}`


This last part has not been explained in the paper but is is necessary for the adequate performance of the method.
For equivalence with the paper [1]_:

- :math:`-B' = -Bs`
- :math:`-G' = -Gs`

.. [1] Rossoni, P. / Moreti da Rosa, W. / Antonio Belati, E., Linearized AC Load Flow
    Applied to Analysis in Electric Power Systems, IEEE Latin America Transactions,
    14, 9; 4048-4053, 2016
