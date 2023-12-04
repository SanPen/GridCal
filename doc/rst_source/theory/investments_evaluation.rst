======================
Investments evaluation
======================

Introduction
_______

Planning power grids involves determining an appropriate set of assets that makes sense from both the
technical and economical optics. This challenge can be understood as an optimization problem, where one tries to
minimize the total cost :math:`C = CAPEX+OPEX`, while simultaneously minimizing the technical restrictions
:math:`t_r`. While apparently simple to comprehend, such a problem in its original form is arduous to solve and a
satisfying solution may not even be reached.

At this point we have to ask ourselves what the underlying issue is. If the puzzle is rigorously formulated, it
becomes of the type MINLP. Not only it can include continuous variables (such as the rating of a substation), but
also a wide set of integer variables (the potential investments to make). It is well-known that even solving a
single-period OPF with only continuous variables becomes a very complicated problem, to the point where the
original scenario is often convexified to solve it with acceptable precision and time. Now imagine we have to find a
solution to such a problem, but considering the full 8760 hours in a year and thousands of investment combinations.
The result would be catastrophic given the astronomically high computational time.

Hence, it is clear we desire an algorithm that can provide us with a list of optimal investments and not suffer from
the curse of dimensionality. The methodology we have adopted here consists of:

#. Building a machine-learning model that captures the behavior of the grid under diverse scenarios.
#. Optimizing such a model in a matter of a few seconds.

Formulation
_______

1. **Objective function**

The selected objective function considers both technical and economical criteria. In particular, it is defined as:

.. math::
    f_o(x) = \sum{C_l(x)_{br}} + \sum C_o(x)_{br} + \sum C_vm(x)_b + \sum C_va(x)_b + \sum CAPEX(x)_i + \sum OPEX(x)_i

where :math:`C_l` is a penalty function associated with active power losses, :math:`C_o` accounts for branch
overloadings, :math:`C_vm` gathers the undervoltage and overvoltage module penalties, and :math:`C_va` represents the
voltage angle deviation penalties. Power losses and the overloadings are calculated for every branch
of the grid :math:`br`, the voltage-related costs are computed at every bus :math:`b` and the CAPEX and OPEX are related
to each active investment :math:`i`. Note here that the unknown :math:`x` is used to represent the investment
combination under consideration.That is, :math:`x` has to be seen as a vector that contains an :math:`n`-length
set of boolean variables that account for the activated or deactivated investments:

.. math::
    x = [x_1, x_2, ..., x_n]

or in compact form, equivalently, :math:`x \in \mathbb{Z}^n_2`.

Given potential differences in the order of magnitude of the different costs, it is decided to normalize the calculated
costs by dividing the sum by the highest value obtained each iteration. Additionally, the user may want to give more
importance to some costs rather than others, to implement this differentiation, each cost is multiplied by a user-defined weight.
Then, the objective function ends up:

.. math::
    f_o(x) = w_l \frac{\sum C_l(x)_{br}}{||C_l(x)||} + w_o \frac{\sum C_o(x)_{br}}{||C_o(x)||} +
    w_{vm} \frac{\sum C_vm(x)_b}{||C_vm(x)||} + w_{vp} \frac{\sum C_{vp}(x)_b}{||C_{vp}(x)||} +
    w_{cx} \frac{\sum CAPEX(x)_i}{||CAPEX(x)||} + w_{ox} \frac{\sum OPEX(x)_i}{||OPEX(x)||}

2. **Costs calculation**

Active power losses are calculated directly from the simulation results, such as power flow results.
All branches, including lines, transformers, DC lines, etc., are considered. The losses are summed to get :math:`C_l(x)`.

For branch overloadings, the procedure is similar. The loading of each branch is computed from simulation results, and
branches with loads above 100% of the rating are penalized. The penalty is calculated by multiplying the associated
overload cost and the loading:

.. math::

    \sum{C_o(x)_{br}} = \sum_{idx \in {branches\_idx}} P_o[idx] \cdot loading[idx] ,

where :math:`branches\_idx` is the set of indices where :math:`loading > 1` and :math:`P_o` is the
corresponding overload penalization of the branch .

Regarding the undervoltages and overvoltages, the associated penalty is computed as:

.. math::
    C_{vm}(x) =  P_{vm} \cdot ( \max(V_m - V^{\text{max}}_m, 0) +  \max(V^{\text{min}}_m - V_m, 0) )

where :math:`V_m , V^{\text{max}}_m, V^{\text{min}}_m, P_{vm}` are vectors containing voltage module results, allowed
maximum voltage, minimum voltage limit and voltage module penalization for each bus.

Testing
_______

In order to test the algorithm for different variations of the objective function, a 130-bus grid has been prepared with
389 Investment Candidates including lines and buses. The diagram of the grid is shown in Figure 1.

.. figure:: ../figures/investments/130bus_grid_diagram.png
    :alt: 130bus-grid diagram
    :scale: 50 %

    Figure 1: Test grid diagram. Grey lines and repeated elements are investment candidates.

Añadir pruebas diferentes weight CAPEX
Añadir figures


.. figure:: ../figures/investments/Figure_1_w_capex-e-6.png
    :alt: Results1
    :scale: 50 %
