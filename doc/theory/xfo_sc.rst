.. _xfo_sc:

Transformer definition from SC test values
==========================================

The transformers are modeled as π branches too. In order to get the series impedance and shunt admittance of
the transformer to match the branch model, it is advised to transform the specification sheet values of the device
into the desired values. The values to take from the specs sheet are:

- :math:`S_n`: Nominal power in MVA.
- :math:`U_{hv}`: Voltage at the high-voltage side in kV.
- :math:`U_{lv}`: Voltage at the low-voltage side in kV.
- :math:`U_{sc}`: Short circuit voltage in %.
- :math:`P_{cu}`: Copper losses in kW.
- :math:`I_0`: No load current in %.
- :math:`GX_{hv1}`: Reactance contribution to the HV side. Value from 0 to 1.
- :math:`GR_{hv1}`: Resistance contribution to the HV side Value from 0 to 1.

Then, the series and shunt impedances are computed as follows:

- Nominal impedance HV (Ohm): :math:`Zn_{hv} = U_{hv}^2 / S_n`
- Nominal impedance LV (Ohm): :math:`Zn_{lv} = U_{lv}^2 / S_n`
- Short circuit impedance (p.u.): :math:`z_{sc} = U_{sc} / 100`
- Short circuit resistance (p.u.): :math:`r_{sc} = \frac{P_{cu} / 1000}{S_n}`
- Short circuit reactance (p.u.): :math:`x_{sc} = \sqrt{z_{sc}^2 - r_{sc} ^2}`
- HV resistance (p.u.): :math:`r_{cu,hv} = r_{sc} \cdot GR_{hv1}`
- LV resistance (p.u.): :math:`r_{cu,lv} = r_{sc} \cdot (1 - GR_{hv1})`
- HV shunt reactance (p.u.): :math:`xs_{hv} = x_{sc} \cdot GX_{hv1}`
- LV shunt reactance (p.u.): :math:`xs_{lv} = x_{sc} \cdot (1 - GX_{hv1})`

If :math:`P_{fe} > 0` and :math:`I0 > 0`, then:

- Shunt resistance (p.u.): :math:`r_{fe} = \frac{Sn}{P_{fe} / 1000}`
- Magnetization impedance (p.u.): :math:`z_m = \frac{1}{I_0 / 100}`
- Magnetization reactance (p.u.): :math:`x_m = \frac{1}{\sqrt{\frac{1}{z_m^2} - \frac{1}{r_{fe}^2}}}`
- Magnetizing resistance (p.u.): :math:`r_m = \sqrt{x_m^2 - z_m^2}`

else:

- Magnetization reactance (p.u.): :math:`x_m = 0`
- Magnetizing resistance (p.u.): :math:`r_m = 0`

The final complex calculated parameters in per unit are:

- Magnetizing impedance (or series impedance): :math:`z_{series} = Z_m = r_{m} +j \cdot x_m`
- Leakage impedance (or shunt impedance): :math:`Z_l = r_{sc} + j \cdot x_{sc}`
- Shunt admittance: :math:`y_{shunt} = 1 / Z_l`

Inverse definition of SC values from π model
--------------------------------------------

In GridCal I found the need to find the short circuit values (:math:`P_{cu}, V_{sc}, r_{fe}, I0`) from the branch values (*R*, *X*, *G*, *B*). Hence the following formulas:

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

