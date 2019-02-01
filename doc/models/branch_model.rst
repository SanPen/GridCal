.. _branch_model:

Universal Branch Model
======================

The following describes the model that is applied to each type of admittance matrix in the `apply_to()` function inside the `Branch` object seen before. The model implemented to describe the behavior of the transformers and lines is the π model.

.. figure:: ../figures/pi-trafo.png
    :alt: π model of a branch

    π model of a branch
    
To define the π branch model we need to specify the following magnitudes:

- :math:`z_{series}`: Magnetizing impedance or simply series impedance in per unit.
- :math:`y_{shunt}`: Leakage impedance or simply shunt impedance in per unit.
- tap_module: Module of the tap changer, magnitude around 1.
- tap_angle: Angle of the tap changer in radians.

In order to apply the effect of a branch to the admittance matrices, first we compute the complex tap value.

.. math::

    tap = tap\_module \cdot e^{−j \cdot tap\_angle}

Then we compose the equivalent series and shunt admittance values of the branch. Both values are complex.

.. math::

    Y_s = \frac{1}{z_{series}}

.. math::

    Y_{sh} = \frac{y_{shunt}}{2}

- :math:`z_{series}`: Complex series impedance of the branch composed by the line resistance and its inductance.
- :math:`y_{shunt}`: Complex shunt admittance of the line composed by the conductance and the susceptance.

Ybranch
-------

The general branch model is represented by a 2×2 matrix.

.. math::

    Y_{branch}=\left( \begin{array}{ccc}
    Y_{ff} & Y_{ft} \\
    Y_{tf} & Y_{tt} \end{array} \right)

In this matrix, the elements are the following:

.. math::

    Y_{ff} = \frac{Y_s + Y_{sh}}{tap \cdot conj(tap)}

.. math::

    Y_{ft} = - Y_s / conj(tap)

.. math::

    Y_{tf} = - Y_s / tap

.. math::

    Y_{tt} = Y_s + Y_{sh}

Ybus
----

The branch admittance values are applied to the complete admittance matrix as follows:

.. math::

    {Y_{bus}}_{f, f} = {Y_{bus}}_{f, f} + Y_{ff}

.. math::

    {Y_{bus}}_{f, t} = {Y_{bus}}_{f, t} + Y_{ft}

.. math::

    {Y_{bus}}_{t, f} = {Y_{bus}}_{t, f} + Y_{tf}

.. math::

    {Y_{bus}}_{t, t} = {Y_{bus}}_{t, t} + Y_{tt}


These formulas assume that there might be something already in :math:`Y_{bus}`, therefore the right way to modify these values is to add the own branch values.

Yshunt
------

.. math::

    {Y_{shunt}}_f = {Y_{shunt}}_f + Y_{sh}

.. math::

    {Y_{shunt}}_t = {Y_{shunt}}_t + \frac{Y_{sh}}{tap \cdot conj(tap)}

Yseries
-------

.. math::

    {Y_{series}}_{f, f} = {Y_{series}}_{f, f} + \frac{Y_{s}}{tap \cdot conj(tap)}

.. math::

    {Y_{series}}_{f, t} = {Y_{series}}_{f, t} + Y_{ft}

.. math::

    {Y_{series}}_{t, f} = {Y_{series}}_{t, f} + Y_{tf}

.. math::

    {Y_{series}}_{t, t} = {Y_{series}}_{t, t} + Y_{s}

Yf and Yt
---------

.. math::

    {Y_f}_{i, f} = {Y_f}_{i, f} + Y_{ff}

.. math::

    {Y_f}_{i, t} = {Y_f}_{i, t} + Y_{ft}

.. math::

    {Y_t}_{i, f} = {Y_t}_{i, f} + Y_{tf}

.. math::

    {Y_t}_{i, t} = {Y_t}_{i, t} + Y_{tt}

Here *i* is the index of the branch in the circuit and *f*, *t* are the corresponding bus indices.

