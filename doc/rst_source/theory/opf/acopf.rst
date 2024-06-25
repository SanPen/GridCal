AC - Optimal Power Flow using an Interior Point Solver
==========================================================

Planning the generation for a given power network is typically done using DC - Optimal Power Flow, a method that relies on approximating the power flow as a linear problem to speed up the process in exchange of precision.
There are works that seek to solve the full non-linear problem, being one of the most relevant the MATPOWER software. The work described in this technical note integrates the Matpower Interior Point Solver in the GridCal environment using Python with the goal of adding new electrical modelling functionalities (such as including transformer operating point optimization or relaxation of the constraints to have a faster case study methodology).

The present document outlines the main additions in this regard, including:

- The model construction from a GridCal object.
- Objective function and constraints definition.
- KKT conditions and Newton-Raphson method.
- Interior Point Solver.
- Optimization output.

1. Grid model
---------------
The two main objects needed to build an electrical grid are buses and branches. The buses are the points where consumption and generation of electricity occur, and branches are the interconnections between buses that transport electricity from points with excess of generation to points lacking electricity. Some of this buses, known as *slack* buses, serve as references for voltage modulus and phase for the rest of the buses.

The final topology of the grid will be given by bus connectivity matrices, where the standard direction of the flow is also stored identifying the *from* and the *to* buses as the origin and destination respectively. This distinction is important, as it will determine the direction of the flow alongside the sign of the branch power.

Generators are the third object that have to be considered when modelling the electrical grid. We need at least 1 generator in order for the grid to have any sense. If only on bus has a generator, we directly identify this node as the *slack* bus. With more generator buses, we will identify those who will be teh reference of the grid (typically will be buses with high and stable power capacity).
Each grid has its generator connectivity matrix, and each generator has its own cost function, considered to be quadratic in this work as shown in the following chapters.

Operational limits of each elements have to be gathered to establish the constraints for buses, lines and generators.

GridCal objects are identified by the class *NumericalCircuit*, which can be abreviated as *nc*. We can extract from them all the information needed to construct the grid model as shown in the following table:

1.1. Numerical Circuit data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. table::
    
    ==============  ================  ========  ================================================
         name          class_type       unit                   descriptions (size)                 
    ==============  ================  ========  ================================================
    slack           Array(int)                  Array with the slack IDs (:math:`nslack`).
    pv              Array(int)                  Array with the PV buses index (:math:`npv`).
    pq              Array(int)                  Array with the PQ buses index (:math:`npq`).
    from_idx        Array(int)                  Array with the *from* buses IDs (:math:`nl`).
    to_idx          Array(int)                  Array with the *to* buses IDs (:math:`nl`).
    k_m             Array(int)                  Array with the module controllable transformers (:math:`ntapm`).
    k_tau           Array(int)                  Array with the phase controllable transformers (:math:`ntapt`).
    f_disp_hvdc     Array(int)                  Array with the dispatchable DC link *from* buses (:math:`ndc`).
    t_disp_hvdc     Array(int)                  Array with the dispatchable DC link *to* buses (:math:`ndc`).
    f_nd_hvdc       Array(int)                  Array with the non-dispatchable DC link *from* buses (:math:`nndc`).
    t_nd_hvdc       Array(int)                  Array with the non-dispatchable DC link *to* buses (:math:`nndc`).
    gen_disp_idx    Array(int)                  Array with the dispatchable generators index (:math:`nig`).
    gen_undisp_idx  Array(int)                  Array with the non-dispatchable generators index (:math:`nnig`).
    br_mon_idx      Array(int)                  Array with the monitored branches index (:math:`m`).
    Ybus            Matrix(complex)   p.u.      Bus admittance matrix (:math:`nbus \text{ }\times\text{ } nbus`).
    Yf              Matrix(complex)   p.u.      *From* admittance matrix (:math:`nl \text{ }\times\text{ } nbus`).
    Yt              Matrix(complex)   p.u.      *To* admittance matrix(:math:`nl \text{ }\times\text{ } nbus`).
    Cg              Matrix(int)                 Generator connectivity matrix (:math:`nbus \text{ }\times\text{ } ngen`).
    Cf              Matrix(int)                 *From* connectivity matrix (:math:`nl \text{ }\times\text{ } nbus`).
    Ct              Matrix(int)                 *To* connectivity matrix (:math:`nl \text{ }\times\text{ } nbus`).
    Sbase           float             MW        Base power for per unit conversion.
    pf              Array(float)      p.u.      Array with the power factor per gen (:math:`ngen`).
    Sg_undisp       Array(complex)    p.u.      Array with the complex power of non-dispatchable gen (:math:`nnig`).
    Pf_nondisp      Array(float)      p.u.      Array with the power of the non-dispatchable DC links (:math:`ndc`).
    R               Array(float)      p.u.      Array with the resistance per branch (:math:`nl`).
    X               Array(float)      p.u.      Array with the reactance per branch (:math:`nl`).
    Sd              Array(complex)    p.u.      Array with the complex power loads per bus (:math:`nbus`).
    Pg_max          Array(float)      p.u.      Array with the upper bound for active power per gen (:math:`ngen`).
    Pg_min          Array(float)      p.u.      Array with the lower bound for active power per gen (:math:`ngen`).
    Qg_max          Array(float)      p.u.      Array with the upper bound for reactive power per gen (:math:`ngen`).
    Qg_min          Array(float)      p.u.      Array with the lower bound for reactive power per gen (:math:`ngen`).
    Vm_max          Array(float)      p.u.      Array with the upper bound for voltage magnitude per bus (:math:`nbus`).
    Vm_min          Array(float)      p.u.      Array with the lower bound for voltage magnitude per bus (:math:`nbus`).
    rates           Array(float)      p.u.      Array with the upper bound for line loading per branch (:math:`nl`).
    c_0             Array(float)      €         Array with the base cost per generator (:math:`ngen`).
    c_1             Array(float)      €/MWh     Array with the linear cost per generator (:math:`ngen`).
    c_2             Array(float)      €/MWh^2   Array with the quadratic cost per generator (:math:`ngen`).
    c_s             Array(float)      €         Array with the branch slack penalty cost (:math:`m`).
    c_v             Array(float)      €         Array with the voltage slack penalty cost (:math:`nbus`).
    ==============  ================  ========  ================================================

Once all the necessary data has been loaded from the *NumericalCircuit* object, the optimization is ready to run. We will see now the mathematical definition of the problem.

2. Variables, objective function and constraints definition
--------------------------------------------------------------
The problem to be solved has the following structure:

.. math::
    
    \min &\quad f(x)\\
    s.t. &\quad G(x) = 0\\
         &\quad H(x) \leq 0
    
    
where :math:`x` is the vector of variables to optimize, :math:`f(x)` is the objective function, :math:`G(x)` is the vector of equality constraints and :math:`H(x)` is the vector of inequality constraints.

2.1. Variables
^^^^^^^^^^^^^^^^^^^^^^^^
The optimization variables of this problem are:

* **Voltage magnitude** (*v*) of all the buses included in the grid. Note that there is no distinction for slack or PV buses. During a PowerFlow evaluation, these buses would have a known voltage magnitude value, but for this AC-OPF evaluation, we set it as free to avoid overconstraining the model (and also considering them as a variable to optimize).
* **Voltage angle** (:math:`\theta`) of all the buses. We will later see that we consider one bus (the primary *slack* bus) as the reference angle 0 to eliminate the rotating nature of the power flow equations.
* **Active power generation** (:math:`P_g`) of all the dispatchable generators.
* **Reactive power generation** (:math:`Q_g`) of all the dispatchable generators.
* **Transformer tap ratio** (:math:`m_p`) for all the module controllable transformers.
* **Transformer phase shift** (:math:`\tau`) for all the phase controllable transformers.
* **DC link from power** (:math:`P_{DC}`) for all the DC links, using the defined *from* bus as a reference.

Additionally, if the user selects the option to use positive slack variables to relax the voltage and branches constraints, the following variables will be added to the optimization vector:

* **Branch power slack variables** (:math:`sl_{sf}`, :math:`sl_{st}` ) for all the monitored branches.
* **Voltage slack variables** (:math:`sl_{vmax}`, :math:`sl_{vmin}` ) for all the buses.
  
The complete vector of variables is structured as follows:

.. math::

    x = [v, \theta, P_g, Q_g, sl_{sf}, sl_{st}, sl_{vmax}, sl_{vmin}, m_p, \tau, P_{DC}]

The size is the following: 

.. math::

    NV = 2nbus + 2ng + nsl + ntapm + ntapt + ndc

with :math:`nsl = 2nbus + 2m` the number of slacks, obtained from the number of buses and number of monitored branches

2.2. Objective function
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The objective function of an AC-OPF can be defined in many ways, depending on what are we trying to minimize. We can opt to minimize the cost, heat losses, penalties due to overloads or demand mismatching...

In this model, the objective function to minimize corresponds to the sum of the costs of each generator, considered to be quadratic:

.. math::

    \min f(x) = c_2^{\top} Pg^2 + c_1^{\top} Pg + c_0

where :math:`c_2`, :math:`c_1` and :math:`c_0` are the vectors with quadratic, linear and constant costs of the generators.

When the slack variables are used, the objective function will be modified to include the penalties associated:

.. math::

    \min f(x) = c_2^{\top} Pg^2 + c_1^{\top} Pg + c_0 + c_{s}^{\top} (sl_{sf} + sl_{st}) + c_v^{\top} (sl_{vmax} + sl_{vmin})

where :math:`c_s` and :math:`c_v` are the vectors with the penalties associated to the branches and voltage slack variables.

2.3. Equality constraints
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The equality constraints present in the model are the nodal power injection equations, as well as the fixed angle reference and PV voltage magnitude. 

The power flow equations ensure that the power exiting the node equals the power entering. Let :math:`V = ve^{j\theta}` be the vector of complex voltages. The following relationships are calculated
at each iteration to compute the power flow equations:

.. math::
    S^{bus} = V \cdot I_{bus}^* = V \cdot (Y_{bus}^* V^*)\\
    G^{S} = S^{bus} + S_d - C_g[:, gen_{disp_idx}] (Pg + jQg) - Cg[:, gen_{undisp_idx}] Sg_undisp\\

where the operation :math:`(\cdot)` is the element-wise multiplication of two vectors, and the brackets denote the slicing of the vectors or matrices using the indexes of the problem.

Let *link* be the index of one of the links (if there are any). The power flow equations are modified as follows for the buses involved in all the DC links:

.. math::
    G^{S}[fdc[link]] += Pf_DC[link]\\
    G^{S}[tdc[link]] -= Pf_DC[link]

There are additional equality balance for PV buses, those buses who have the same maximum and minimum voltage (which means, their voltage module is controlled) and one equality for the primary *slack* bus, setting its angle as 0.

.. math::
    G^{PV} = v[pv] - Vm_max[pv]\\
    G^{Th} = \theta[slack]

where we use :math:`Vm_max` directly as for PV buses it will be equal to :math:`Vm_min`. Finally, the structure of the equality constraints vector is:

.. math::
    G(x) = [G^{S}.real, G^{S}.imag, G^{PV}, G^{Th}]

where the power balance has been split into the real and imaginary parts to solve a real-valued system of equations. 

2.4. Inequality constraints
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The inequalities correspond to the operational limits for the voltage and power variables, which are dependênt on the bus or generator, and the maximum power allowed through a line. 
This last conditions has to hold on both ends of the line, and it is a quadratic expression in order to use real-valued conditions:

.. math::

    H^{sf} = S^{f^{*}} \cdot S^{f} - S_{max}^2\\
    H^{st} = S^{t^{*}} \cdot S^{t} - S_{max}^2

The rest of the conditions are straight-forward linear inequalities for the maximum and minimum bounds, and are not displayed for simplicity. The complete vector of inequality constraints is:

.. math::

    H(x) = [H^{sf}, H^{st}, H^{vu}, H^{pu}, H^{qu}, H^{vl}, H^{pl}, H^{ql}, H^{slsf}, H^{slst}, H^{slvmax}, H^{slvmin},  H^{tapmu}, H^{taptu}, H^{tapml}, H^{taptl}, H^{dcu}, H^{dcl}]

3. KKT conditions and Newton-Raphson method
--------------------------------------------
Once we have settled our grid model, we want to obtain the optimal solution of it, which will yield the lowest value possible for the objective function. Since we are facing a non-convex problem, there are multiple local optimal points for this problem. This has to be taken into account prior to make any statements about the solution. The point we obtain when solving these problem is a local optimal point, which can be potentially the global optimal point of the problem. More advanced methods will allow us to determine more accurately if there can be better operating points.
A general optimization problem, such as the one we are facing were no simplifications can be made, can be solved by imposing the KKT conditions over the variables of it and solving the resulting system of equations with a numerical method. Here, we use the Newton-Raphson method, explained in this section.

3.1. KKT conditions
^^^^^^^^^^^^^^^^^^^^^^
To formulate the problem using the KKT conditions, we will make use of associated multipliers and slack variables for our set of constraints. We can rewrite the optimization problem as follows:


.. math::
    \min & \quad f(x)\\
    s.t. & \quad G(x) = 0\\
         & \quad H(x) + Z = 0

where :math:`Z` is the slack variable associated to the inequality constraints used to transform them into an equality. Then, we introduce the multipliers :math:`\lambda` and :math:`\mu`, which are associated to the equality and inequality constraints respectively. We can now write the expressions of the KKT conditions for the optimization problem:


.. math::
    L = \nabla f(x) + \lambda^{\top} \nabla G(x) + \mu^{\top} \nabla H(x) = 0 \\
    \mu Z - \gamma = 0 \\
    G(x) = 0 \\
    H(x) + Z = 0\\
    \mu, Z \geq 0

Note that the second condition makes use of the parameter :math:`\gamma`, which starts off at a non-zero value to improve convergence and is updated each iterative step tending to 0.
The last condition will be ensured avoiding steps that reduce below 0 both :math:`\mu` and Z, and not through a direct expression.

3.2. Newton-Raphson method
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
To solve the previous system of equations, we make use of the Newton-Raphson method. The method consists on updating the vector of unknowns based on the following generalized step:

.. math::
    y_{i+1} = y_i + \delta y_i = y_i - \frac{f(y_i)}{f'(y_i)}

In this optimization problem, we have a vector of unknowns composed by the following variables:

.. math::
    y = [x, \lambda, \mu, Z] 


To find the optimization step :math:`\delta y_i`, we will solve the following matricial problem:

.. math::
    -J(y_i) \delta y_i = f(y_i)

Where :math:`J(y_i)` is the jacobian matrix of the system of equations described in the previous section, and :math:`f(y_i)` is a vector with the value of these expressions.
For this general optimization problem, we can reduce the size of this system using the same methodology used in MATPOWER's Interior Point Solver (MIPS), where the reduced system is the following:

.. math::

    \begin{matrix}
    \textbf{M} & \textbf{G_{X}^{\top}} \\
    \textbf{G_{X}} & \textbf{0} \\
    \end{matrix}
    \times
    \begin{matrix}
    \Delta X\\
    \Delta \lambda \\
    \end{matrix}
    =
    \begin{matrix}
    - \textbf{N}\\
    - \textbf{G(X)}\\
    \end{matrix} \\

    \textbf{M} = L_{XX} + H_{X}^{\top} [Z]^{-1}[\mu]H_{X}\\
    \textbf{N} = L_{X} + H_{X}^{\top} [Z]^{-1}(\gamma \textbf(1_{n_i}) +[\mu]H(X))\\
    L_{X} = f_X^{\top} + G_X^{\top}\lambda + H_X^{\top}\mu\\
    L_{XX} = f_{XX} + G_{XX}(\lambda) + H_{XX}(\mu)

where the subindex :math:`X` and :math:`XX` indicate the first and second gradient with respect to the variables vector. 


3.3. Updating step
^^^^^^^^^^^^^^^^^^^^

The Newton-Raphson system will be solved for every given step, and will yield the step distances for the variables (X) and the \lambda multiplier. 
To update the other two objects of the state vector of the complete system, we will use the following relations:

.. math::

    \Delta Z = -H(X) -Z - H_X \Delta X\\
    \Delta \mu = -\mu + [Z]^{-1}(\gamma \textbf(1_{n_i}) - [\mu]\Delta Z)

We could proceed to directly add the obtained displacements to the variables and multipliers, but there are two things to be considered. Firstly, we set a step control to ensure that the next step does not increase the error by more than a set margin. The next block of code includes all the logic behind this control:

.. code-block:: python

    # Step control as in PyPower
        if step_control:
            L = ret.f + np.dot(lam, ret.G) + np.dot(mu, ret.H + z) - gamma * np.sum(np.log(z))
            alpha = 1.0
            for j in range(20):
                dx1 = alpha * dx
                dlam1 = alpha * lam
                dmu1 = alpha * mu

                x1 = x + dx1
                lam1 = lam + dlam1
                mu1 = mu + dmu1

                ret1 = func(x1, mu1, lam1, False, False, *arg)

                L1 = ret1.f + lam.T @ ret1.G + mu.T @ (ret1.H + z) - gamma * np.sum(np.log(z))
                rho = (L1 - L) / (Lx @ dx1 + 0.5 * dx1.T @ Lxx @ dx1)

                if rho_lower < rho < rho_upper:
                    break
                else:
                    alpha = alpha / 2.0
                    ssc = 1
                    print('Use step control!')

            dx = alpha * dx
            dz = alpha * dz
            dlam = alpha * dlam
            dmu = alpha * dmu


Then, as explained earlier, the conditions that :math:`\mu` and Z are always positive are enforced outside the algebraic system. This is done ensuring that the step length of a negative displacement is limited in case it ends below 0.

 .. math::

    \alpha_p = min(\tau \cdot min_{\Delta Z_m < 0}((-Z_m / \Delta Z_m), 1))\\
    \alpha_d = min(\tau \cdot min_{\Delta \mu_m < 0}((-\mu_m / \Delta \mu_m), 1))

Where :math:`\tau` is a parameter slightly below 1. Now, we are ready to update the values for the variables and multiplier, then update the :math:`\gamma` parameter, and finally start a new iteration if the convergence criteria is not met.

.. math::

    X = X + \alpha_p \Delta X\\
    Z = Z + \alpha_p \Delta Z\\
    \lambda = \lambda + \alpha_d \Delta \lambda\\
    \mu = \mu + \alpha_d \Delta \mu\\
    \gamma = \sigma \frac{Z^{\top} \mu}{n_{ineq}}

With \sigma set as a value between 0 and 1 (set by default at 0.1)


4. Calculation of derivatives
-------------------------------

In the solving process of the Newton-Raphson, the first and second derivatives of the objective function and constraints have to be calculated. 

4.1. Objective function
^^^^^^^^^^^^^^^^^^^^^^^^^^

The objective function is a quadratic function that only has dependency with respect to the active power, so its first and second derivatives are:

.. math::
    f = c_2^{\top} Pg^2 + c_1^{\top} Pg + c_0\\
    f_X[2nbus:2nbus+ng] = 2 (c_2 \cdot Pg) + c_1\\
    f_{XX}[2nbus : 2nbus + ng, 2nbus : 2nbus + ng] = 2 [c_2]

where :math:`(a\cdot b)` expresses the element-wise multiplication of two vectors, :math:`nbus` is the number of buses and :math:`ng` is the number of generators. 

In case the slack variables are used, the gradient vector will have some additional terms:

.. math::
    
    f_X[npfvar : npfvar + m] = c_s\\
    f_X[npfvar + m : npfvar + 2m] = c_s\\
    f_X[npfvar + 2m : npfvar + 2m + nbus] = c_v\\
    f_X[npfvar + 2m + nbus : npfvar + 2m + 2nbus] = c_v

where :math:`m` is the number of monitored branches and :math:`npfvar = 2nbus + 2ng` is the number of variables in the base power flow problem.


4.2. Equality constraints
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The equality constraints associated with fixed setpoints (such as PV buses and slack reference) are straight-forward and not shown in here. The relevant derivatives are 
those associated with the power flow equations. The derivatives that are calculated with respect to the base power flow variables can be found at MATPOWER's documentation, while the 
derivatives with respect to the transformer variables have been developed during this work.

4.2.1. First derivatives
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The first derivatives of the power flow equations with respect to the variables are calculated as follows:

.. math::
    \frac{dG^{S}}{dX} = \frac{dS^{bus}}{dX} +  C_g[:, gen_{disp_idx}]\frac{d(Pg + jQg)}{dX} \\ 

The derivatives with respect to the power variables are linear and straight-forward, while the derivatives with respect to voltage and transformer variables are more complicated, 
and involve dealing with the derivatives with respect to the bus injection vector. Following Matpower's work for the base power flow variables, we get:

.. math:: 
    Ibus = Ybus V\\
    \frac{dG^{S}}{dv} = [V] ([Ibus]^* + Ybus^* [V]^*) \left[\frac{1}{v}\right] \\
    \frac{dG^{S}}{d\theta} = j[V] ([Ibus]^* - Ybus^* [V]^*)\\
    \frac{dG^{S}}{dP_g} = -C_g[:, gen_{disp_idx}]\\
    \frac{dG^{S}}{dQ_g} = -jC_g[:, gen_{disp_idx}]

When dealing with derivatives with respect to the transformer variables, the approach chosen has been to decompose the S^{bus} vector into the *from* and *to* branch power vectors, in order to 
avoid dealing with the derivatives of the full admittance matrix, which would mean dealing with higher order tensors. The decomposition used was:

.. math::
    S^{bus} = {C_f}^{\top} S^{f} + {C_t}^{\top} S^{t} \\
    \frac{dS^{bus}}{dX} = {C_f}^{\top} \frac{dS^{f}}{dX} + {C_t}^{\top} \frac{dS^{t}}{dX}

The following expressions extracted from the Flexible Universal Branch Model (FUBM) can be used to obtain the derivatives. Let :math:`k := (f_k, t_k)` describe a branch between 
buses :math:`f` and :math:`t` that includes a transformer with the tap variables :math:`(m_{p_k}, \tau_k)`. The branch powers in both directions can be described as: 

.. math::
    S^{f_k} = V_{f_k} {Y_{ff_k}}^* {V_{f_k}}^* + V_{f_k} Y_{ft_k} {V_{t_k}}^* \\
    S^{t_k} = V_{t_k} {Y_{tf_k}}^* {V_{f_k}}^* + V_{t_k} Y_{tt_k} {V_{t_k}}^* \\
    Y_{ff_k} = \frac{y_{s_k}}{{m_{p_k}}^2} \\
    Y_{ft_k} = -\frac{y_{s_k}}{m_{p_k}} {e}^{-j\tau_k} \\
    Y_{tf_k} = -\frac{y_{s_k}}{m_{p_k}} {e}^{\text{ }j\tau_k} \\
    Y_{tt_k} = y_{s_k}

with :math:`y_{s_k} = \frac{1}{R_k+jX_k}` the series admittance of the branch. A note should be done regarding :math:`(m_p, \tau)`. Even though not all the lines will include transformers,
and even less have controllable transformers, the admittances are calculated using these values for the tap ratio and the phase shift. In case there is no transformer, their value will be set to 
:math:`(1, 0)`, and the derivatives will be 0. In case there is a transformer but it is not controllable, the derivatives will be 0 as well, and the values for the tap variables will take the
nominal value obtained from the grid file. This means, the following derivatives will only be computed for the branches included in the subsets :math:`k_m` and :math:`k_\tau`.

Branches with transformers with module control
+++++++++++++++++++++++++++++++++++++++++++++++

The variable vector :math:`m_p` only contains those transformers which are in a branch included in the list :math:`k_m`, meaning the matrices :math:`\frac{dS_{f/t}}{dm_p}` will be sized 
:math:`nbus \text{ }\times\text{ } ntapm`. Let :math:`k` be a branch with a transformer :math:`(m_{p_i}, \tau_i)` with module control, and :math:`V_f = C_f V`, :math:`V_t = C_t V` 
the voltages at the *from* and *to* buses. The first derivatives with respect to the module are calculated as follows:

.. math::
    \frac{{dS}^{f}}{dm_{p}}_{ki} = -2\frac{{y_{s_k}}^*}{{m_{p_i}}^3} V_{f_k} {V_{f_k}}^* + \frac{{y_{s_k}}^*}{{m_{p_i}}^2{e}^{\text{ }j\tau_i}} V_{f_k}{V_{t_k}}^*\\
    \frac{{dS}^{t}}{dm_{p}}_{ki} = \frac{{y_{s_k}}^*}{{m_{p_i}}^2{e}^{-j\tau_i}} V_{t_k} {V_{f_k}}^* 

Branches with transformers with phase control
++++++++++++++++++++++++++++++++++++++++++++++

We proceed similarly, this time with the transformers which are in a branch included in the list :math:`k_\tau` (note that some of them will already appear in the previous list, which 
means they will have crossed second derivatives). The matrices :math:`\frac{dS_{f/t}}{d\tau}` will be sized :math:`nbus \text{ }\times\text{ } ntapt`. The 
first derivatives with respect to the phase shift are calculated as follows:

.. math::
    \frac{{dS}^{f}}{d\tau}_{ki} = j\frac{{y_{s_k}}^*}{{m_{p_i}}{e}^{\text{ }j\tau_i}} V_{f_k}{V_{t_k}}^*\\
    \frac{{dS}^{t}}{d\tau}_{ki} = -j\frac{{y_{s_k}}^*}{{m_{p_i}}{e}^{-j\tau_i}} V_{t_k} {V_{f_k}}^*


The final step to get the derivatives with respect to the transformer variables is to recover the :math:`\frac{dSbus}{dX}` using the compositions of the *from* and *to* branch power vectors:

.. math::
    \frac{dS^{bus}}{dm_p} = {C_f}^{\top} \frac{dS^{f}}{dm_p} + {C_t}^{\top} \frac{dS^{t}}{dm_p}\\
    \frac{dS^{bus}}{d\tau} = {C_f}^{\top} \frac{dS^{f}}{d\tau} + {C_t}^{\top} \frac{dS^{t}}{d\tau}

4.2.2. Second derivatives
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Developing the second derivatives is quite more complicated. The only terms of the hessian matrix :math:`G_{XX}(\lambda)` that are non-zero are those that depend on the voltage variables and the 
transformer variables, since the first derivatives with respect to power variables are constant. We start off by developing the full expression of the Lagrangian gradient, were these second 
derivatives appear:

.. math:: 
    L_X = \nabla(f_X) + \nabla(\lambda^{\top} G_X) + \nabla(\mu^{\top} H_X)\\

which means that the second derivative is not the direct derivative of the first derivative, since it has to include the multiplier. In addition, since 
the constraints have been separated into real and imaginary, the active and reactive power multipliers :math:`\lambda_p = \lambda[0 : nbus]` and :math:`\lambda_q = \lambda[nbus : 2nbus]` 
have to be added to the corresponding constraints accordingly. The following second derivatives with respect 
to the voltage variables have been adapted from Matpower's work to include this real and imaginary separation:

.. math::
    G_{vv_p} = \left[ \frac{1}{v} \right] (C_p + C_p^{\top}) + \left[ \frac{1}{v^2} \right] \\
    G_{v\theta_p} = j \left[ \frac{1}{v} \right] (I_p - F_p) \\
    G_{\theta\theta_p} = I_p + F_p \\

where:

.. math::
    I_p = [V]^* ({Ybus^*}^{\top} [V]^* [\lambda_p] - [{Ybus^*}^{\top} [V]^* \lambda_p])\\
    F_p = [\lambda_p] [V] (Ybus^*[V]^* - [Ibus]^*) \\
    C_p = [\lambda_p] [V] Ybus^*[V]^* 

And identically, but using :math:`\lambda_q`, for the reactive power derivatives. To compose again the full hessian matrix, the following expressions are used:

.. math:: 
    G_{vv} = \mathcal{R}(G_{vv_p}) + \mathcal{I}(G_{vv_q}) \\
    G_{v\theta} = \mathcal{R}(G_{v\theta_p}) + \mathcal{I}(G_{v\theta_q}) \\
    G_{\theta v} = G_{v\theta}^{\top}
    G_{\theta\theta} = \mathcal{R}(G_{\theta\theta_p}) + \mathcal{I}(G_{\theta\theta_q}) 

This ensures that only the active power balance is multiplied by the active power multiplier, and equally for the reactive power balance. 

Now, following the path used in the first derivatives with respect to the transformer variables, the second derivatives of the branch powers have to be obtained. In this case, there 
will be crossed derivatives with respect to the voltage variables of both buses involved, which will make the process considerably more complex.


Branches with transformers with module control
+++++++++++++++++++++++++++++++++++++++++++++++

Firstly, the branch power derivatives are calculated for the branches in the list :math:`k_{m}`:

.. math:: 
    \frac{d^2S^{f}}{dm_p^2}_{ki} = 6\frac{{y_{s_k}}^*}{{m_{p_i}}^4} V_{f_k} {V_{f_k}}^* - 2\frac{{y_{s_k}}^*}{{m_{p_i}}^3{e}^{\text{ }j\tau_i}} V_{f_k}{V_{t_k}}^*\\
    \frac{d^2S^{t}}{dm_p^2}_{ki} = 2\frac{{y_{s_k}}^*}{{m_{p_i}}^3{e}^{-j\tau_i}} V_{t_k} {V_{f_k}}^* \\
    
    \frac{d^2S^{f}}{dm_p d\tau}_{ki} = -2j\frac{{y_{s_k}}^*}{{m_{p_i}^2{e}^{\text{ }j\tau_i}}} V_{f_k}{V_{t_k}}^*\\
    \frac{d^2S^{t}}{dm_p d\tau}_{ki} = 2j\frac{{y_{s_k}}^*}{{m_{p_i}^2{e}^{-j\tau_i}}} V_{t_k}{V_{f_k}}^*\\
    \frac{d^2S^{f}}{d\tau^2}_{ki} = -\frac{{y_{s_k}}^*}{{m_{p_i}{e}^{\text{ }j\tau_i}}} V_{f_k}{V_{t_k}}^*\\
    \frac{d^2S^{t}}{d\tau^2}_{ki} = \frac{{y_{s_k}}^*}{{m_{p_i}{e}^{-j\tau_i}}} V_{t_k}{V_{f_k}}^*

Hessian matrix
^^^^^^^^^^^^^^^^^^^^^^^^
.. math::

   G_XX = \begin{bmatrix}
     & (pv \cup pq) & (pq) & (ng) & (ng) & (k_\tau) & (k_m) \\
    (pv \cup pq) & G_{va, va} & G_{va, vm} & 0 & 0 & G_{va, \tau} & G_{va, m}\\
    (pq) & G_{vm, va} & G_{vm, vm} & 0 & 0 & G_{vm, \tau} & G_{vm, m}\\
    (ng) & 0 & 0 & 0 & 0 & 0 & 0 \\
    (ng) & 0 & 0 & 0 & 0 & 0 & 0 \\
    (k_\tau) & G_{\tau, va} & G_{\tau, vm} & 0 & 0 & G_{\tau, \tau} & G_{\tau, m}\\
    (k_m) & G_{m, va} & G_{m, vm} & 0 & 0 & G_{m, \tau} & G_{m, m}\\
    \end{bmatrix}



















