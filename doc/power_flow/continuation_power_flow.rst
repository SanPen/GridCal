

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
    J & \frac{\partial F}{\partial \lambda} \\
    \frac{\partial P}{\partial V} & \frac{\partial P}{\partial \lambda} \\
    \end{bmatrix}
    \times
    \begin{bmatrix}
    \Delta\theta\\
    \Delta|V|\\
    \lambda
    \end{bmatrix}
    =
    \begin{bmatrix}
    0^\hat \\
    0^\hat \\
    1\\
    \end{bmatrix}

Corrector
---------
