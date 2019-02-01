.. _newton_raphson:

Newton-Raphson-Iwamoto
======================

The Newton-Raphson method is the standard power flow method tough at schools. GridCal implements a slight but important modification of this method that turns it into a more robust, industry-standard algorithm. The Newton Raphson method is the first order Taylor approximation of the power flow equation. The method implemented in GridCal is the second order approximation, let's see how.

The expression to update the voltage solution in the Newton-Raphson algorithm is the following:

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

The formulation implemented in GridCal includes the optimal acceleration parameter *µ*:

.. math::

    \textbf{V}_{t+1} = \textbf{V}_t + \mu \textbf{J}^{-1}(\textbf{S}_0 - \textbf{S}_{calc})

Here *µ* is the Iwamoto optimal step size parameter. In 1982 S. Iwamoto and Y. Tamura present a method \cite{iwamoto1981load} where the Jacobian matrix *J* is only computed at the beginning, and the iteration control parameter *µ* is computed on every iteration. In GridCal I compute *J* and *µ* on every iteration getting a more robust method on the expense of a greater computational effort.

To compute the parameter *µ* we must do the following:

.. math::

    \textbf{J'} = Jacobian(\textbf{Y}, \textbf{dV})
    \textbf{dx} = \textbf{J}^{-1}(\textbf{S}_0 - \textbf{S}_{calc})
    \textbf{a} = \textbf{S}_0 - \textbf{S}_{calc}
    \textbf{b} = \textbf{J} \times \textbf{dx}
    \textbf{c} = \frac{1}{2} \textbf{dx} \cdot (\textbf{J'} \times \textbf{dx})

.. math::

    g_0 = -\textbf{a} \cdot \textbf{b}
    g_1 = \textbf{b} \cdot \textbf{b} + 2  \textbf{a} \cdot \textbf{c}
    g_2 = -3  \textbf{b} \cdot \textbf{c}
    g_3 = 2  \textbf{c} \cdot \textbf{c}

.. math::

    G(x) = g_0 + g_1x + g_2x^2 + g_3x^3

.. math::

    µ = solve(G(x), x_0=1)

There will be three solutions to the polynomial *G(x)*. Only the last solution will be real, and therefore it is the only valid value for *µ*.
The polynomial can be solved numerically using *1* as the seed.

The matrix :math:`\textbf{J'}` is the Jacobian matrix computed using the voltage derivative numerically computed as the voltage increment :math:`\textbf{dV}= \textbf{V}_{t} - \textbf{V}_{t-1}` (voltage difference between the current and the previous iteration).  

Jacobian
--------

The Jacobian matrix is the derivative of the power flow equation for a given voltage set of values.

.. math::

    \textbf{J} =
    \begin{bmatrix}
    \textbf{J}_{11} & \textbf{J}_{12} \\
    \textbf{J}_{21} & \textbf{J}_{22} \\
    \end{bmatrix}

Where:

- J11 = :math:`Re\left(\frac{\partial \textbf{S}}{\partial \theta}[pvpq, pvpq]\right)`
- J12 = :math:`Re\left(\frac{\partial \textbf{S}}{\partial |V|}[pvpq, pq]\right)`
- J21 = :math:`Im\left(\frac{\partial \textbf{S}}{\partial \theta}[pq, pvpq]\right)`
- J22 = :math:`Im\left(\frac{\partial \textbf{S}}{\partial |V|}[pq pq]\right)`

Where:

- :math:`\textbf{S} = \textbf{V} \cdot (\textbf{I} + \textbf{Y}_{bus} \times \textbf{V})^*`

Here we introduced two complex-valued derivatives:

- :math:`\frac{\partial S}{\partial \theta} = V_{diag} \cdot (Y_{bus} \times V_{diag,norm})^* + I_{diag}^* \cdot V_{diag,norm}` 
- :math:`\frac{\partial S}{\partial |V|} =  1j \cdot V_{diag} \cdot (I_{diag} - Y_{bus} \times V_{diag})^*`

Where:

- :math:`V_{diag}`: Diagonal matrix formed by a voltage solution.
- :math:`V_{diag,norm}`: Diagonal matrix formed by a voltage solution, where every voltage is divided by its module.
- :math:`I_{diag}`: Diagonal matrix formed by the current injections.
- :math:`Y_{bus}`: And of course, this is the circuit full admittance matrix.

This Jacobian form can be used for other methods.

