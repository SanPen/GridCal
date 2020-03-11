.. _holomorphic_embedding:

Holomorphic Embedding
=====================

First introduced by Antonio Trias in 2012 [1]_, promises to be a non-divergent power
flow method. Trias originally developed a version with no voltage controlled nodes
(PV), in which the convergence properties are excellent (With this software try to
solve any grid without PV nodes to check this affirmation). 

The version programmed in GridCal has been adapted from the outstanding contribution
by Josep Fanals Batllori. This version includes a formulation of the voltage controlled nodes
that is competitive with the traditional methods.

GridCal's integration contains a vectorized version of the algorithm. This means that
the execution in python is much faster than a previous version that uses loops.

Concepts
--------

All the power flow algorithms until the HELM method was introduced were iterative and
recursive. The helm method is iterative but not recursive. A simple way to think of
this is that traditional power flow methods are exploratory, while the HELM method is
a planned journey.

The fundamental idea of the recursive algorithms is that given a voltage initial point
(1 p.u. at every node, usually) the algorithm explores the surroundings of the initial
point until a suitable voltage solution is reached (the algorithm converges) or no solution
at all is found because the initial point is supposed to be *far* from the solution.

On the HE method, we form a *curve* that departures from a known mathematically
exact solution that is obtained from solving the grid with no power injections.
This is possible because with no power injections, the grid equations become linear and
straight forward to solve. The arriving point of the *curve* is the solution that we
want to achieve. The *curve* is a convergent series of terms that approximates the
voltage. The convergence of the series approximation to the point of interest can be
enhanced by using series approximants functions like the Padè, Epsylon, Sigma, etc. that
enhance the rate at which the series of coefficients reach a solution.

The HE formulation consists in the derivation of formulas that enable the calculation
of the coefficients of the series that describes the *curve* from the mathematically
know solution to the unknown solution. Once the coefficients are obtained, a simple summation or
the accelerated approximation computes the voltage solution at the *end of the curve*, providing the
desired voltage solution. The more coefficients we compute the more exact the solution
is since the series is a convergent one. This is true until the numerical precision limit is reached.

All this sounds very strange, but it works ;)

If you want to get familiar with this concept, you should read about the homotopy
concept. In practice the continuation power flow does the same as the HE algorithm,
it takes a known solution and changes the loading factors until a solution for another
state is reached.

.. _fundamentals:

Fundamentals
------------

The fundamental equation that defines the power flow problem is:

.. _base_eq:

.. math::
    
    \textbf{Y} \times \textbf{V} = \textbf{I}^*

Where :math:`\textbf{Y}` is the admittance matrix, :math:`\textbf{V}` is the nodal voltages vector and
:math:`\textbf{I}` is the nodal current injections vector. To be able to solve this equation we need to
specify at least one of the voltages (the slack node voltage). This leads to a reduced system and the
appearance of extra nodal injection currents derived from the voltage source (the slack) that we have
just removed:


.. math::

    \textbf{Y}_{red} \times \textbf{V}_{red} = \textbf{I}_{red}^* - \textbf{I}_{slack}

We also need to split the admittance matrix :math:`Y` into :math:`Y_{series}` and :math:`Y_{shunt}`.
:math:`Y_{shunt}` could be stored as a vector, but for mathematecal accuracy, let's deal with it as a
diagonal matrix. The following relation should hold:

.. math::

    Y_{red} = Y_{red, series} + Y_{red, shunt}

Substituting and rearranging we should have:

.. math::

    \textbf{Y}_{red, series} \times \textbf{V}_{red} = \textbf{I}^*_{red}  -\textbf{I}_{slack} - \textbf{Y}_{red, shunt} \times \textbf{V}_{red}

It is necessary to express the nodal current injections in terms of the specified power:


.. math::

    \textbf{Y}_{red, series} \times \textbf{V}_{red} = \frac{\textbf{S}_{red}^*}{\textbf{V}_{red}^*} - \textbf{I}_{slack} - \textbf{Y}_{red, shunt} \times \textbf{V}_{red}


The holomorphic embedding is to insert a "travelling" parameter :math:`\alpha`, such
that for :math:`\alpha=0` we have an mathematically exact solution of the problem in the no-load situation,
and for :math:`\alpha=1` we have the solution for the specified load situation (the one we're looking for)


.. _base_eq_alpha_0:

.. math::

    \textbf{Y}_{red, series} \times \textbf{V}_{red}(\alpha) = \frac{\alpha \cdot \textbf{S}_{red}^*}{\textbf{V}_{red}^*(\alpha^*)} - \textbf{I}_{slack}(\alpha) - \alpha \cdot \textbf{Y}_{red, shunt} \times \textbf{V}_{red}(\alpha)

For :math:`\alpha=0` the power term becomes zero, in this way the equation becomes linear, and its
solution is mathematically exact. This will be useful later. Now we need to express all the
magnitudes that are a function of :math:`\alpha` into McLaurin series.


Wait, what?? did you just made this stuff up??

So far the reasoning is:

- The voltage :math:`\textbf{V}` is what we have to convert into a series, and the
  series depend of :math:`\alpha`, so it makes sense to say that :math:`\textbf{V}`,
  as it is dependent of :math:`\alpha`, becomes :math:`\textbf{V}(\alpha)`.

- The slack currents :math:`\textbf{I}_{slack}` are formed as a function of the voltage
  at the slack nodes, hence they turn into an :math:`\alpha`-dependent series too.

- Regarding the :math:`\alpha` values multiplying :math:`\textbf{S}` and
  :math:`\textbf{Y}_{shunt}`, they are there to provoke the first
  voltage coefficients to be one in the no load situation (:math:`\alpha=0`). This is
  essential for the obtaining of convergent series.

- The asterisk in the :math:`\alpha` of the term :math:`\frac{\alpha \cdot \textbf{S}^*}{\textbf{V}^*(\alpha^*)}`
  is explained below. In short, it is there to ensure that the Cauchy-Riemann condition is met.

The series are expressed as McLaurin equations:

.. _McLaurinV:

.. math::

    V(\alpha) = \sum_{n}^{\infty} V_n \alpha ^n

**Theorem - Holomorphicity check** There's still something to do. The magnitude
:math:`\left(\textbf{V}( \alpha )\right)^*` has to be converted into
:math:`\left(\textbf{V}( \alpha^* )\right)^*`. This is done in order to make the
function be holomorphic. The holomorphicity condition is tested by the
Cauchy-Riemann condition, this is
:math:`\partial \textbf{V} / \partial \alpha^* = 0`, let's check that:

.. math::

    \partial \left(\textbf{V}( \alpha )^*\right) / \partial \alpha^*  = \partial \left(\sum_{n}^{\infty} V_n^* (\alpha ^n)^*\right) / \partial \alpha^*  = \sum_{n}^{\infty} \alpha ^n V_n^* (\alpha ^{n-1})^*

Which is not zero, obviously. Now with the proposed change:

.. math::

    \partial \left( \textbf{V}( \alpha^* )\right)^* / \partial \alpha^*  = \partial \left(\sum_{n}^{\infty} \textbf{V}_n^* \alpha ^n \right) / \partial \alpha^*  = 0
    
Yes!, now we're mathematically happy, since this stuff has no effect in practice because our :math:`\alpha`
is not going to be a complex parameter.

**(End of Theorem)**

..
    The fact that we have :math:`\textbf{V}^*( \alpha^* )` dividing is problematic. We need to
    express it as its inverse so it multiplies instead of divide.

    .. math::

        \frac{1}{\textbf{V}( \alpha)} =
        \textbf{W}( \alpha ) \longrightarrow \textbf{W}( \alpha ) \textbf{V}( \alpha) = 1
        \longrightarrow \sum_{c=0}^{\infty}{\textbf{W}_c \alpha^c}
        \sum_{c=0}^{\infty}{\textbf{V}_c \alpha^c} = 1

    Expanding the series and identifying terms of :math:`\alpha` we obtain the expression
    to compute the inverse voltage series coefficients:

    .. math::

        \textbf{W}_c =
        \left\{
            \begin{array}{ll}
                \frac{1}{\textbf{V}_0}, \quad c=0 \\
                -\frac{{\sum_{k=0}^{c}\textbf{W}_k \textbf{V}_{c-k}}}{\textbf{V}_0}, \quad c>0
            \end{array}
        \right.

    Now, :ref:`this equation<base_eq_embedded2>` becomes:

    .. _base_eq_embedded3:

    .. math::

        {\textbf{Y}_{series}\times \textbf{V}( \alpha )} =
        \alpha\textbf{S}^* \cdot \textbf{W}( \alpha)^*
        - \alpha \textbf{Y}_{shunt} \textbf{V}( \alpha )

    Substituting the series by their McLaurin expressions:

    .. _base_eq_embedded4:

    .. math::

        {\textbf{Y}_{series}\times \sum_{n=0}^{\infty}{\textbf{V}_n \alpha^n}} = \alpha\textbf{S}^* \left(\sum_{n=0}^{\infty}{\textbf{W}_n \alpha^n}\right)^*  - \alpha \textbf{Y}_{shunt} \sum_{n=0}^{\infty}{\textbf{V}_n \alpha^n}

    Expanding the series an identifying terms of :math:`\alpha` we obtain the expression
    for the voltage coefficients:

    .. math::

        \textbf{V}_n =
        \left\{
            \begin{array}{ll}
                {0}, \quad n=0\\
                {\textbf{S}^* \textbf{W}^*_{n-1} - Y_{shunt} \textbf{V}_{n-1} }, \quad n>0
            \end{array}
        \right.

    This is the HELM fundamental formula derivation for a grid with no voltage controlled
    nodes (no PV nodes). Once a sufficient number of coefficients are obtained, we still
    need to use the Padè approximation to get voltage values out of the series.

    In the previous formulas, the number of the bus has not been explicitly detailed. All
    the :math:`\textbf{V}` and the :math:`\textbf{W}` are matrices of dimension
    :math:`n \times nbus` (number of coefficients by number of buses in the grid) This
    structures are depicted in the figure
    :ref:`Coefficients Structure<coefficients_structure>`. For instance
    :math:`\textbf{V}_n` is the :math:`n^{th}` row of the coefficients structure
    :math:`\textbf{V}`.

    .. _coefficients_structure:

    .. figure:: ../../figures/coefficients_structure.png
        :alt: Coefficients Structure

        Coefficients Structure




Implementation
------------------

What we want with the method is to compute order after order the terms of the voltage series which will
provide the nodal voltage of the reduced grid (this is ok, because we know the slack voltages already).
Therefore, in our case we want to compute the complex voltage (:math:`U`) at the PQ and PV nodes of the grid, and
the reactive power at the PV nodes (:math:`Q`).

As explained before, we are working with an equivalent grid that contains no slack nodes, since we have
reduced then and replaced their influence by current injections (:math:`I_{slack}`) Hence, the number
of nodes in the number of PQ nodes plus the number of PV nodes.

.. figure:: ../../figures/matrix-reduction.png
    :alt: Matrix reduction (VD: Slack, PV: Voltage controlled, PQ: Power controlled)

In this implementation the lists denoted as pq and pv, are referred to the reduced grid, not to the complete grid.
To remember this is of capital importance because the dimensions belong to a grid with :math:`n - n\_slack=npqpv` nodes.

Also, from the mathematical derivation we have concluded that we have three kinds of coefficients;
The first ones (:math:`c=0`) that will provide the zero-load solution, the second ones (:math:`c=1`)
and the rest (:math:`c>1`). The coefficients of order 0 require no system solution whatsoever.
It also to be noted that the system matrix is computed and factorized only once. The resulting series are perfectly
convergent so that you may find the nodal voltage by a simple voltage coefficient summation.

We will store three kinds of coefficients:

- :math:`U[ncoeff, npqpv]`: Complex voltage coefficients for all the nodes of the reduced scheme.
- :math:`W[ncoeff, npqpv]`: Complex inverse voltage coefficients for all the nodes of the reduced scheme.
  The exist because dividing a series by another is too hard, and thus we came up with the inverse to be
  able to operate the coefficient divisions via convolutions.
- :math:`Q[ncoeff, npv]`: Reactive power coefficients at the PV nodes. These are to be able to compute
  the voltage while keeping the voltage module set.


Linear system
^^^^^^^^^^^^^^

This is the linear system of equations that is to be solved for coefficient orders greater than 0 (:math:`c>0`):

.. math::

    \begin{bmatrix}
    G_{red} & -B_{red} & -diag(Im\{W[0]\})\\
    B_{red} & G_{red} & diag(Re\{W[0]\})\\
    diag(2 \cdot V_{re}[0]) & diag(2 \cdot V_{im}[0]) & 0
    \end{bmatrix} \times \begin{bmatrix}
    U_{re}^{(c}\\
    U_{im}^{(c}\\
    Q^{(c}
    \end{bmatrix} = \begin{bmatrix}
    RHS_{pq}^{(c}\\
    RHS_{pv}^{(c}\\
    RHS_{Q}^{(c}
    \end{bmatrix}

The updating of the voltage and PV-node reactive power coefficient arrays is done like this:

.. math::

    U[c, :] = U_{re}^{(c} + j \cdot U_{im}^{(c}

    Q[c, :] = Q^{(c}

    W[c, :] = -W[c-1, :] \cdot \frac{U[c, :]^*}{U[c-1, :]^*}

C=0
^^^^^^^

.. math::

    U[0, :] = Y_{red}^{-1} \times Y_{slack}

    W[0, :] = \frac{1}{U[0, :]^*}

C=1
^^^^^^^

.. math::

    I_{inj} = Y_{slack} \times V_{slack}

.. math::

    RHS_{pq}^{(1} = I_{inj}[pq] - Y_{slack}[pq] + S_{red}[pq] \cdot W[0, pq] - Y_{shunt\_red, pq} \cdot U[0, pq]

    RHS_{pv}^{(1} = I_{inj}[pv] - Y_{slack}[pv] + P_{red}[pv] \cdot W[0, pv] - Y_{shunt\_red, pv} \cdot U[0, pv]

    RHS_{Q}^{(1} = |V_{red}[pv]|^2 - Re \left\{U[0, pv] \cdot U[0, pv]^* \right\}


C>1
^^^^^^^

.. math::

    RHS_{pq}^{(c} = S_{red}[pq] \cdot W[c-1, pq] - Y_{shunt\_red}[pq] \cdot U[c-1, pq]

    RHS_{pv}^{(c} = -j \cdot W[:, pv] \circledast Q[:,pv] + P_{red}[pv] \cdot W[c-1, pv] - Y_{shunt\_red}[pv] \cdot U[c-1, pv]

    RHS_{Q}^{(c} = -Re \left\{U[:, pv] \circledast U[:, pv]^* \right\}

The :math:`\circledast` symbol is the convolution symbol.

Finding the voltage
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The simplest way to find the voltage is to sum the coefficients.

.. math::

    V_i = \sum_k^{ncoeff} U[k, i]

More refined methods might accelerate the obtaining of the voltage. This is that a more accurate solution
can be obtained with less coefficients computed. For instance the Padè approximation.


Padè approximation
--------------------

The :ref:`McLaurinV equation<McLaurinV>` provides us with an expression to obtain the voltage from
the coefficients, knowing that for :math:`\alpha=1` we get the final voltage results.
So, why do we need any further operation?, and what is this Padè thing?

Well, it is true that the :ref:`McLaurinV equation<McLaurinV>` provides an approximation of the
voltage by means of a series (this is similar to a Taylor approximation), but in
practice, the approximation might provide a wrong value for a given number of
coefficients. The Padè approximation accelerates the convergence of any given series,
so that you get a more accurate result with less coefficients. This means that for the
same series of voltage coefficients, using the :ref:`McLaurinV equation<McLaurinV>` could give a
completely wrong result, whereas by applying Padè to those coefficients one could
obtain a fairly accurate result.

The Padè approximation is a rational approximation of a function. In our case the
function is :math:`\textbf{V}(\alpha)`, represented by the coefficients structure
:math:`\textbf{V}`. The approximation is valid over a small domain of the function, in
our case the domain is :math:`\alpha=[0,1]`. The method requires the function to be
continuous and differentiable for :math:`\alpha=0`. Hence the Cauchy-Riemann condition.
And yes, our function meets this condition, we tested it before.

GridCal implements two algorithms that perform the Padè approximation; The Padè
canonical algorithm, and Wynn's Padè approximation.

**Padè approximation algorithm**

The canonical Padè algorithm for our problem is described by:

.. _pade_apprx:

.. math::

    Voltage\_value\_approximation = \frac{P_N(\alpha)}{Q_M(\alpha)} \quad \forall \alpha \in [0,1]

Here :math:`N=M=n/2`, where :math:`n` is the number of available voltage coefficients,
which has to be an even number to be exactly divisible by :math:`2`. :math:`P` and
:math:`Q` are polynomials which coefficients :math:`p_i` and :math:`q_i` must be
computed. It turns out that if we make the first term of :math:`Q_M(\alpha)` be
:math:`q_0=1`, the function to be approximated is given by the McLaurin expression
(What a happy coincidence!)

.. math::

    P_N(\alpha) = p_0 + p_1\alpha + p_2\alpha^2 + ... + p_N\alpha^N

.. math::

    Q_M(\alpha) = 1 + q_1\alpha + q_2\alpha^2 + ... + q_M\alpha^M

The problem now boils down to find the coefficients :math:`q_i` and :math:`p_i`. This
is done by solving two systems of equations. The first one to find :math:`q_i` which
does not depend on :math:`p_i`, and the second one to get :math:`p_i` which does depend
on :math:`q_i`.

**First linear system**: The only unknowns are the :math:`q_i` coefficients.

.. math::

    \begin{matrix}
    q_M V_{N-M+1} + q_{M-1}V_{N-M+2}+...+q_1V_N = 0\\
    q_M V_{N-M+2} + q_{M-1}V_{N-M+3}+...+q_1V_{N+1} = 0\\
    ...\\
    q_M V_{N} + q_{M-1}V_{N+1}+...+q_1V_{N+M+1} + V_{N+M} = 0\\
    \end{matrix}

**Second linear System**: The only unknowns are the :math:`p_i` coefficients.

.. math::

    \begin{matrix}
    V_0 - p_0=0\\
    q_1V_0 + V_1  p_1=0\\
    q_2V_0 + q_1V_1+V_2-p_2=0\\
    q_3V_0 + q_2V_1 + q_1V_2 + V_3 - p_3 = 0\\
    ...\\
    q_MV_{N-M} + q_{M-1}V_{N-M+1} + ... + +V_N - p_N=0
    \end{matrix}

Once the coefficients are there, you would have defined completely the polynomials
:math:`P_N(\alpha)` and :math:`Q_M(\alpha)`, and it is only a matter of evaluating the
:ref:`Padè approximation equation<pade_apprx>` for :math:`\alpha=1`.

This process is done for every column of coefficients
:math:`\textbf{V}=\{V_0, V_1,V_2,V_3, ...,V_n\}` of the structure depicted in the
:ref:`coefficients structure figure<coefficients_structure>`. This means that we have
to perform a Padè approximation for every node, using the one columns of the voltage
coefficients per Padé approximation.

**Wynn's Padè approximation algorithm**

Wynn published a paper in 1969 [4]_ where he proposed a simple calculation method to
obtain the Padè approximation. This method is based on a table. Weniger in 1989
publishes his thesis [5]_ where a faster version of Wynn's algorithm is provided in
Fortran code.

That very Fortran piece of code has been translated into Python and included in GridCal.

One of the advantages of this method over the canonical Padè approximation
implementation is that it can be used for every iteration. In the beginning I thought
it would be faster but it turns out that it is not faster since the amount of
computation increases with the number of coefficients, whereas with the canonical
implementation the order of the matrices does not grow dramatically and it is executed
the half of the times.

On top of that my experience shows that the canonical implementation provides a more
consistent convergence.

Anyway, both implementations are there to be used in the code.


.. [1] Trias, Antonio. "The holomorphic embedding load flow method." Power and Energy Society General Meeting, 2012 IEEE. IEEE, 2012.

.. [2] Subramanian, Muthu Kumar. Application of holomorphic embedding to the power-flow problem. Diss. Arizona State University, 2014.

.. [4] Wynn, P. "The epsilon algorithm and operational formulas of numerical analysis." Mathematics of Computation 15.74 (1961): 151-158.

.. [5] Weniger, Ernst Joachim. "Nonlinear sequence transformations for the acceleration of convergence and the summation of divergent series." Computer Physics Reports 10.5-6 (1989): 189-371.
