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

1. **Basic objective function**

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
1. **Grid**

In order to test the algorithm for different variations of the objective function, a 130-bus grid has been prepared with
389 Investment Candidates including lines and buses. The diagram of the grid is shown in Figure 1.

.. figure:: ../figures/investments/130bus_grid_diagram.png
    :alt: 130bus-grid diagram
    :scale: 50 %

    Figure 1: Test grid diagram. Grey lines and repeated elements are investment candidates.

2. **Base case**

Initially, the algorithm did not include the economical criteria in the objective function. Although it is clear that it
is needed to somehow include the CAPEX and OPEX to the minimization, the results obtained are useful to grasp the effect
of including economical criterion.

.. figure:: ../figures/investments/Figure_1_wo_capex.png
    :alt: Results wo CAPEX
    :scale: 50 %

    Figure 2: Paretto plot for investments evaluation without CAPEX.

It is clear in Figure 2 that the more investments are selected, the lower the technical criteria are and, therefore, the
lower the objective function. Hence, the algorithm learns that more investments equal minimum objective function values.
By adding the CAPEX to the objective function, it is expected to correct this tendency and instead find an optimal point
regarding both technical and economic criteria.

3. **Initial tests**

Including the CAPEX in the objective function is a delicate problem. As seen in Figure 2, the CAPEX values can be above
:math:`10^4` while the technical criteria are below :math:`10^{-1}`. Therefore, when adding these values to the objective
function, the CAPEX will inherently have more weight and unbalance the results.

As an example, the reader can find below the graphs corresponding to multiplying the CAPEX by different minimization
factors

.. figure:: ../figures/investments/Figure_1_w_capex-e-6_v2.png
    :alt: Results CAPEX 10^-6
    :scale: 50 %

    Figure 3: Results obtained when CAPEX is multiplied by :math:`10^{-6}`.

.. figure:: ../figures/investments/Figure_1_w_capex-e-5_v2.png
    :alt: Results CAPEX 10^-5
    :scale: 50 %

    Figure 4: Results obtained when CAPEX is multiplied by :math:`10^{-5}`.

.. figure:: ../figures/investments/Figure_1_w_capex-e-4_v2.png
    :alt: Results CAPEX 10^-4
    :scale: 50 %

    Figure 5: Results obtained when CAPEX is multiplied by :math:`10^{-4}`.

.. figure:: ../figures/investments/Figure_1_w_capex-e-3_v2.png
    :alt: Results CAPEX 10^-3
    :scale: 50 %

    Figure 6: Results obtained when CAPEX is multiplied by :math:`10^{-3}`.

The previous figures show that the more disparate the economic and technical criterion are, the more likely is the
objective function to tend to lesser investments solutions. The situation from the Base case is reverted,
but another problem arises: How should the different criteria values be computed so that all elements in the objective
function are around the same order of magnitude?

4. **Normalization**
When dealing with multicriteria optimization, it is common to establish some reference values for each criteria in
the objective function and normalize the terms by dividing the factors by the reference point. In essence, the basic
objective function presented in Formulation would be modified as:

.. math::
    f_o(x) = \frac{\sum{C_l(x)_{br}}}{l_{ref}} + \frac{\sum C_o(x)_{br}}{o_{ref}} + \frac{\sum C_vm(x)_b}{vm_{ref}} +
    \frac{\sum C_va(x)_b}{va_{ref}} + \frac{\sum CAPEX(x)_i}{CAPEX_{ref}} + \frac{\sum OPEX(x)_i}{OPEX_{ref}}

However, given the nature of the problem being solved, it is not possible to determine reference values for each
criteria beforehand. Hence, one proposed solution consists in taking the values of the terms for the first iteration
with investments, compute scaling factors referent to that iteration as:

.. math::
    sf_{i} = \frac{mean_i}{min(mean)}

being:

    - :math:`sf_{i}`: the scale factor for each :math:`i` criteria; losses scaling factor, overload scaling factor, etc.),
    - :math:`mean_i`: the mean between the maximum and minimum value of each criteria; :math:`\frac{max(losses) + min(losses)}{2}`,
    - :math:`mean`: an array of all the computed means of the factors; :math:`[mean_{losses}, mean_{overload}, mean_{vm}, ... ]`.

The results obtained from this normalization can be seen in Figure 7.

.. figure:: ../figures/investments/Figure_2_normalization.png
    :alt: First normalization results
    :scale: 50 %

    Figure 7: Results obtained for the first normalization type.