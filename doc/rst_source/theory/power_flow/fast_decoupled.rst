.. _fast_decoupled:

Fast Decoupled
===================

The fast decoupled method is a fantastic power flow algorithm developed by Stott and Alsac [FD]_.
The method builds on a series of very clever simplifications and the decoupling of the Jacobian matrix of the
canonical Newton-Raphson algorithm to yield the fast-decoupled method.

The method consists in the building of two admittance-based matrices :math:`B'` and :math:`B''` which are
independently factorized (using the LU method or any other) which then serve to find the increments of angle
and voltage magnitude separately until convergence.

Finding :math:`B'` and :math:`B''`
----------------------------------------

To find :math:`B'` we perform the following operations:

.. math::

    bs' = \frac{1}{X}

    bs'_{ff} = diag(bs')

    bs'_{ft} = diag(-bs')

    bs'_{tf} = diag(-bs')

    bs'_{tt} = diag(bs')

    B'_f = bs'_{ff} \times Cf + bs'_{ft} \times Ct

    B'_t = bs'_{tf} \times Cf + bs'_{tt} \times Ct

    B' = Cf^\top \times B'_f + Ct^\top \times B'_t

To find :math:`B''` we perform the following operations:

.. math::

    bs_{ff}^{''} = -Re \left\{\frac{bs' + B}{tap \cdot tap^*} \right\}

    bs_{ft}^{''}  = -Re \left\{ \frac{bs'}{tap^*} \right\}

    bs_{tf}^{''} = -Re \left\{ \frac{bs'}{tap} \right\}

    bs_{tt}^{''} = - bs''

    B''_f = bs''_{ff} \times Cf + bs''_{ft} \times Ct

    B''_t = bs''_{tf} \times Cf + bs''_{tt} \times Ct

    B'' = Cf^\top \times B''_f + Ct^\top \times B''_t


The fast-decoupled algorithm
-------------------------------

- Factorize :math:`B'`

    .. math::

        J1 = factorization(B')

- Factorize :math:`B''`

    .. math::

        J2 = factorization(B'')

- Compute the voltage module :math:`V_m = |V|`

- Compute the voltage angle :math:`V_a= atan \left ( \frac{V_i}{V_r} \right )`

- Compute the error

    .. math::

        S_{calc} = V \cdot \left( Ybus \times V - I_{bus} \right)^*

    .. math::

        \Delta S = \frac{S_{calc} - S_{bus}}{V_m}

    .. math::

        \Delta P = Re \left\{\Delta S[pqpv] \right\}

    .. math::

        \Delta Q = Im \left\{ \Delta S[pq] \right\}

- Check the convergence

    .. math::
        converged = |\Delta P|_{\infty} < tol \quad \&  \quad|\Delta Q|_{\infty}  < tol


- Iterate; While convergence is false and the number of iterations is less than the maximum:


    - Solve voltage angles (P-iteration)

        .. math::

            \Delta V_a = J1.solve( \Delta P)

    - Update voltage

        .. math::

            V_a[pqpv] = V_a[pqpv] - \Delta V_a

            V = V_m \cdot e^{j \cdot V_a}

    - Compute the error (follow the previous steps)
    - Check the convergence (follow the previous steps)

    - If the convergence is still false:

        - Solve voltage modules (Q-iteration)

            .. math::

                \Delta V_m = J2.solve( \Delta Q)

        - Update voltage

            .. math::

                V_m[pq] = V_m[pq] - \Delta V_m

                V = V_m \cdot e^{j \cdot V_a}

        - Compute the error (follow the previous steps)
        - Check the convergence (follow the previous steps)

    - Increase the iteration counter.

- End

.. [FD] B. Stott and O. Alsac, 1974, Fast Decoupled Power Flow, IEEE Trasactions PAS-93 859-869.