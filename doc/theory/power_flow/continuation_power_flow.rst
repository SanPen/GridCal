

Continuation power flow
^^^^^^^^^^^^^^^^^^^^^^^

The continuation power flow is a technique that traces a trajectory from a base situation given to a combination
of power :math:`S_0` and voltage :math:`V_0`, to another situation determined by another combination of power
:math:`S'`. When the final power situation is undefined, then the algorithm continues until the Jacobian is singular,
tracing the voltage collapse curve.

The method uses a predictor-corrector technique to trace this trajectory.

Predictor
---------

.. math::

    \begin{bmatrix}
        \theta \\
        V \\
        \lambda \\
    \end{bmatrix}^{predicted}
    =
    \begin{bmatrix}
            \theta \\
            V \\
            \lambda \\
        \end{bmatrix}^{i}
    +
    \sigma \cdot
    \begin{bmatrix}
        J11  &  J12  & P_{base} \\
        J21  &  J22  & Q_{base} \\
        0    & 0    & 1 \\
    \end{bmatrix}^{-1}
    \times
    \begin{bmatrix}
        \hat{0} \\
        \hat{0} \\
        1\\
    \end{bmatrix}

Corrector
---------

.. math::

    \begin{bmatrix}
        d\theta \\
        dV \\
        d\lambda \\
    \end{bmatrix}
    =
    \begin{bmatrix}
            d\theta_0\\
            dV_0 \\
            d\lambda_0 \\
        \end{bmatrix}
    +
    \sigma \cdot
    \begin{bmatrix}
        J11  &  J12  & P_{base} \\
        J21  &  J22  & Q_{base} \\
        0    & -1    & 0 \\
    \end{bmatrix}^{-1}
    \times
    \begin{bmatrix}
        \hat{0} \\
        \hat{0} \\
        1\\
    \end{bmatrix}


