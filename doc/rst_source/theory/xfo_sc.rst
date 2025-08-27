.. _xfo_sc:

Transformer definition from SC test values
==========================================

The transformers are modeled as π branches too. In order to get the series impedance and shunt admittance of
the transformer to match the branch model, it is advised to transform the specification sheet values of the device
into the desired values. The values to take from the specs sheet are:

- :math:`S_n`: Nominal power in MVA.
- :math:`HV`: Voltage at the high-voltage side in kV.
- :math:`LV`: Voltage at the low-voltage side in kV.
- :math:`V_{hv\_bus}`: Nominal voltage of the high-voltage side bus kV.
- :math:`V_{lv\_bus}`: Nominal voltage of the low-voltage side bus kV.
- :math:`V_{sc}`: Short circuit voltage in %.
- :math:`P_{cu}`: Copper losses in kW.
- :math:`I_0`: No load current in %.
- :math:`Share_{hv1}`: Contribution to the HV side. Value from 0 to 1.


Short circuit impedance (p.u. of the machine)

.. math::

    z_{sc} = \frac{V_{sc}}{100}

Short circuit resistance (p.u. of the machine)

.. math::

    r_{sc} = \frac{P_{cu} / 1000}{ S_n }


Short circuit reactance (p.u. of the machine)
Can only be computed if :math:`r_{sc} < z_{sc}`

.. math::

    x_{sc} = \sqrt{z_{sc}^2 - r_{sc}^2}

Series impedance (p.u. of the machine)

.. math::

    z_s = r_{sc} + j \cdot x_{sc}


The issue with tis is that we now must convert :math:`zs` from machine base to the system base.

First we compute the High voltage side:

.. math::

    z_{base}^{HV} = \frac{HV^2}{S_n}

    z_{base}^{hv\_bus} = \frac{V_{hv\_bus}^2}{S_{base}}

    z_{s\_HV}^{system}  = z_s\cdot  \frac{z_{base}^{HV}}{z_{base}^{hv\_bus}} \cdot Share_{hv1}  = z_s \cdot  \frac{HV^2 \cdot S_{base}}{V_{hv\_bus}^2 \cdot S_n}  \cdot Share_{hv1}


Now, we compute the Low voltage side:

.. math::

    z_{base}^{LV} = \frac{LV^2}{S_n}

    z_{base}^{lv\_bus} = \frac{V_{lv\_bus}^2}{S_{base}}

    z_{s\_LV}^{system} = z_s \cdot \frac{z_{base}^{LV}}{z_{base}^{lv\_bus}}  \cdot (1 - Share_{hv1})  = z_s \cdot  \frac{LV^2 \cdot S_{base}}{V_{lv\_bus}^2 \cdot S_n}  \cdot (1 - Share_{hv1})



Finally, the system series impedance in p.u. is:

.. math::

    z_s = z_{s\_HV}^{system} + z_{s\_LV}^{system}


Now, the leakage impedance (shunt of the model)

.. math::

    r_m = \frac{S_{base}}{P_{fe} / 1000}


.. math::

    z_m = \frac{100 \cdot S_{base}}{I0 \cdot S_n}


.. math::

    x_m = \sqrt{\frac{ - r_m^2 \cdot z_m^2}{z_m^2 - r_m^2}}


Finally the shunt admittance is (p.u. of the system):

.. math::

    y_{shunt} = \frac{1}{r_m} + j \cdot \frac{1}{x_m}


Inverse definition of SC values from π model
--------------------------------------------

In VeraGrid I found the need to find the short circuit values (:math:`P_{cu}, V_{sc}, r_{fe}, I0`) from the branch values (*R*, *X*, *G*, *B*). Hence the following formulas:

.. math::

    z_{sc} = \sqrt{R^2 + X^2}

.. math::

    V_{sc} = 100 \cdot z_{sc}

.. math::

    P_{cu} = R \cdot S_n \cdot 1000

.. math::

    zl = 1 / (G + j B)

.. math::

    r_{fe} = zl.real

.. math::

    xm = zl.imag

.. math::

    I0 = 100 \cdot \sqrt{1 / r_{fe}^2 + 1 / xm^2}

