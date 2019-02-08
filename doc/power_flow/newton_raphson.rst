.. _newton_raphson:

Newton-Raphson
==============

All the explanations on this section are implemented `here
<https://github.com/SanPen/GridCal/blob/master/src/GridCal/Engine/Numerical/jacobian_based_power_flow.py>`_.

.. _canonical_nr:

Canonical Newton-Raphson
------------------------

The Newton-Raphson method is the standard power flow method tough at schools.
**GridCal** implements slight but important modifications of this method that turns it
into a more robust, industry-standard algorithm. The Newton-Raphson method is the first
order Taylor approximation of the power flow equation.

The expression to update the voltage solution in the Newton-Raphson algorithm is the
following:

.. math::

    \textbf{V}_{t+1} = \textbf{V}_t + \textbf{J}^{-1}(\textbf{S}_0 - \textbf{S}_{calc})

Where:

- :math:`\textbf{V}_t`: Voltage vector at the iteration *t* (current voltage).
- :math:`\textbf{V}_{t+1}`: Voltage vector at the iteration *t+1* (new voltage).
- :math:`\textbf{J}`: Jacobian matrix.
- :math:`\textbf{S}_0`: Specified power vector.
- :math:`\textbf{S}_{calc}`: Calculated power vector using :math:`\textbf{V}_t`.

In matrix form we get:

.. math::

    \begin{bmatrix}
    \textbf{J}_{11} & \textbf{J}_{12} \\
    \textbf{J}_{21} & \textbf{J}_{22} \\
    \end{bmatrix}
    \times
    \begin{bmatrix}
    \Delta\theta\\
    \Delta|V|\\
    \end{bmatrix}
    =
    \begin{bmatrix}
    \Delta \textbf{P}\\
    \Delta \textbf{Q}\\
    \end{bmatrix}

.. _jacobian:

Jacobian in power equations
---------------------------

The Jacobian matrix is the derivative of the power flow equation for a given voltage
set of values.

.. math::

    \textbf{J} =
    \begin{bmatrix}
    \textbf{J}_{11} & \textbf{J}_{12} \\
    \textbf{J}_{21} & \textbf{J}_{22} \\
    \end{bmatrix}

Where:

- :math:`J11 = Re\left(\frac{\partial \textbf{S}}{\partial \theta}[pvpq, pvpq]\right)`
- :math:`J12 = Re\left(\frac{\partial \textbf{S}}{\partial |V|}[pvpq, pq]\right)`
- :math:`J21 = Im\left(\frac{\partial \textbf{S}}{\partial \theta}[pq, pvpq]\right)`
- :math:`J22 = Im\left(\frac{\partial \textbf{S}}{\partial |V|}[pq pq]\right)`

Where:

- :math:`\textbf{S} = \textbf{V} \cdot \left(\textbf{I} + \textbf{Y}_{bus} \times \textbf{V} \right)^*`

Here we introduced two complex-valued derivatives:

- :math:`\frac{\partial S}{\partial |V|} = V_{diag} \cdot \left(Y_{bus} \times V_{diag,norm} \right)^* + I_{diag}^* \cdot V_{diag,norm}`
- :math:`\frac{\partial S}{\partial \theta} =  1j \cdot V_{diag} \cdot \left(I_{diag} - Y_{bus} \times V_{diag} \right)^*`

Where:

- :math:`V_{diag}`: Diagonal matrix formed by a voltage solution.
- :math:`V_{diag,norm}`: Diagonal matrix formed by a voltage solution, where every voltage is divided by its module.
- :math:`I_{diag}`: Diagonal matrix formed by the current injections.
- :math:`Y_{bus}`: And of course, this is the circuit full admittance matrix.

This Jacobian form can be used for other methods.

Newton-Raphson-Iwamoto
----------------------

In 1982 S. Iwamoto and Y. Tamura present a method [1]_  where the
:ref:`Jacobian<jacobian>` matrix *J* is only computed at the beginning, and the
iteration control parameter *µ* is computed on every iteration. In **GridCal**, *J* and
*µ* are computed on every iteration getting a more robust method on the expense of a
greater computational effort.

The Iwamoto and Tamura's modification to the :ref:`Newton-Raphson<canonical_nr>`
algorithm consist in finding an optimal acceleration parameter *µ* that determines the
length of the iteration step such that, the very iteration step does not affect
negatively the solution process, which is one of the main drawbacks of the
:ref:`Newton-Raphson<canonical_nr>` method:

.. math::

    \textbf{V}_{t+1} = \textbf{V}_t + \mu \cdot \textbf{J}^{-1}\times (\textbf{S}_0 - \textbf{S}_{calc})

Here *µ* is the Iwamoto optimal step size parameter. To compute the parameter *µ* we
must do the following:

.. math::

    \textbf{J'} = Jacobian(\textbf{Y}, \textbf{dV})

The matrix :math:`\textbf{J'}` is the :ref:`Jacobian<jacobian>` matrix computed using
the voltage derivative numerically computed as the voltage increment
:math:`\textbf{dV}= \textbf{V}_{t} - \textbf{V}_{t-1}` (voltage difference between the
current and the previous iteration).

.. math::
    \textbf{dx} = \textbf{J}^{-1} \times  (\textbf{S}_0 - \textbf{S}_{calc})

    \textbf{a} = \textbf{S}_0 - \textbf{S}_{calc}

    \textbf{b} = \textbf{J} \times \textbf{dx}

    \textbf{c} = \frac{1}{2} \textbf{dx} \cdot (\textbf{J'} \times \textbf{dx})

.. math::

    g_0 = -\textbf{a} \cdot \textbf{b}

    g_1 = \textbf{b} \cdot \textbf{b} + 2  \textbf{a} \cdot \textbf{c}

    g_2 = -3  \textbf{b} \cdot \textbf{c}

    g_3 = 2  \textbf{c} \cdot \textbf{c}

.. math::

    G(x) = g_0 + g_1 \cdot x + g_2 \cdot x^2 + g_3 \cdot x^3

.. math::

    µ = solve(G(x), x_0=1)

There will be three solutions to the polynomial :math:`G(x)`. Only the last solution
will be real, and therefore it is the only valid value for :math:`µ`. The polynomial
can be solved numerically using *1* as the seed.

.. [1] Iwamoto, S., and Y. Tamura. "A load flow calculation method for ill-conditioned power systems."IEEE transactions on power apparatus and systems 4 (1981): 1736-1743.

.. _nr_line_search:

Newton-Raphson Line Search
--------------------------

The method consists in adding a heuristic piece to the
:ref:`Newton-Raphson<canonical_nr>` routine. This heuristic rule is to set µ=1, and
decrease it is the computed error as a result of the voltage update is higher than
before. The logic here is to decrease the step length because the update might have
gone too far away. The proposed rule is to divide µ by 4 every time the error
increases. There are more sophisticated ways to achieve this, but this rule proves to
be useful.

The algorithm is then:

    1. Start.

    2. Compute the power mismatch vector :math:`F` using the initial voltage solution :math:`V`.

    3. Compute the error. Equation \ref{eq:nr_error}.

    4. While :math:`error > tolerance` or :math:`iterations < max\_iterations`:

        a. Compute the Jacobian

        b. Solve the linear system.

        c. Set :math:`\mu = 1`.

        d. Assign :math:`\Delta x` to :math:`V`.

        e. Compute the power mismatch vector :math:`F` using the latest voltage solution :math:`V`.

        f. Compute the error.

        g. If the :math:`error^{k} > error^{k-1}` from the previous iteration:

            g1. Decrease :math:`\mu = 0.25 \cdot \mu`

            g2. Assign :math:`\Delta x` to :math:`V`.

            g3. Compute the power mismatch vector :math:`F` using the latest voltage solution :math:`V`.

            g4. Compute the error.

        h. :math:`iterations = iterations + 1`

    5. End.

The :ref:`Newton-Raphson<canonical_nr>` method tends to diverge if the grid is not
perfectly balanced in loading and well conditioned (i.e.: the impedances are not wildly
different in per unit and X>R). The control parameter :math:`\mu` turns the
:ref:`Newton-Raphson<canonical_nr>` method into a more controlled method that converges
in most situations.

Newton-Raphson in Current Equations
-----------------------------------

:ref:`Newton-Raphson<canonical_nr>` in current equations is similar to the regular
:ref:`Newton-Raphson<canonical_nr>` algorithm presented before, but the mismatch is
computed with the current instead of power.

The :ref:`Jacobian<jacobian>` is then:

.. math::

    J=
    \left[
    \begin{array}{cc}
    Re\left\{\left[\frac{\partial I}{\partial \theta}\right]\right\}_{(pqpv, pqpv)} &
    Re\left\{\left[\frac{\partial I}{\partial Vm}\right]\right\}_{(pqpv, pq)} \\
    Im\left\{\left[\frac{\partial I}{\partial \theta}\right]\right\}_{(pq, pqpv)} &
    Im\left\{\left[\frac{\partial I}{\partial Vm}\right]\right\}_{(pq,pq)}
    \end{array}
    \right]

Where:

.. math::

    \left[\frac{\partial I}{\partial Vm}\right] = [Y] \times [E_{diag}]

.. math::

    \left[\frac{\partial I}{\partial \theta}\right] = 1j \cdot [Y] \times [V_{diag}]

The mismatch is computed as increments of current:

.. math::

    F = \left[
    \begin{array}{c}
     Re\{\Delta I\} \\
     Im\{\Delta I\}
    \end{array}
    \right]

Where:

.. math::

    [\Delta I] = \left( \frac{S_{specified}}{V} \right)^*  - ([Y] \times [V] - [I^{specified}])

The steps of the algorithm are equal to the the algorithm presented in :ref:`Newton-Raphson<canonical_nr>`.
