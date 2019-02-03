.. _levenberg_marquardt:

Levenberg-Marquardt
===================

The Levenberg-Marquardt iterative method is often used to solve non-linear least
squares problems. in those problems one reduces the calculated error by
iteratively solving a system of equations that provides the increment to add to the
solution in order to decrease the solution error. So conceptually it applies to the
power flow problem.

Set the initial values:

- :math:`\nu = 2`
- :math:`f_{prev} = 10^9`
- :math:`ComputeH = true`

In every iteration:

- Compute the jacobian matrix if `ComputeH` is `true`:

.. math::

    \textbf{H} = Jacobian(\textbf{Y}, \textbf{V})

- Compute the mismatch in the same order as the jacobian:

.. math::

    \textbf{S}_{calc} = \textbf{V} (\textbf{Y} \cdot \textbf{V} - \textbf{I})^*

.. math::

    \textbf{m} = \textbf{S}_{calc} - \textbf{S}

.. math::

    \textbf{dz} = [ Re(\textbf{m}_{pv}), Re(\textbf{m}_{pq}), Im(\textbf{m}_{pq})]

- Compute the auxiliary jacobian transformations:

.. math::

    \textbf{H}_1 = \textbf{H}^\top

.. math::

    \textbf{H}_2 = \textbf{H}_1 \cdot \textbf{H}

- Compute the first value of :math:`\lambda` (only in the first iteration):

.. math::

    \lambda = 10^{-3} Max(Diag(\textbf{H}_2))

- Compute the system Matrix:

.. math::

    \textbf{A} = \textbf{H}_2 + \lambda \cdot Identity

- Compute the linear system right hand side:

.. math::

    \textbf{rhs} = \textbf{H}_1 \cdot \textbf{dz}

- Solve the system increment:

.. math::

    \textbf{dx} = Solve(\textbf{A}, \textbf{rhs})

- Compute the objective function:

.. math::

    f = 0.5 \cdot \textbf{dz} \cdot \textbf{dz}^\top

- Compute the decision function:

.. math::

    \rho = \frac{f_{prev}-f}{0.5 \cdot \textbf{dx}^\top \cdot (\lambda \textbf{dx} + \textbf{rhs})}

- Update values:

    If :math:`\rho > 0`

    - :math:`ComputeH = true`
    - :math:`\lambda = \lambda \cdot max(1/3, 1- (2 \cdot \rho -1)^3)`
    - :math:`\nu = 2`
    - Update the voltage solution using :math:`\textbf{dx}`.

    Else

    - :math:`ComputeH = false`
    - :math:`\lambda = \lambda \cdot \nu`
    - :math:`\nu = \nu \cdot 2`

- Compute the convergence:

.. math::

    converged = ||dx, \infty|| < tolerance

- :math:`f_{prev} = f`

As you can see it takes more steps than Newton-Raphson. It is a slower method, but it
works better for ill-conditioned and large grids.
