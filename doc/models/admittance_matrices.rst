.. _admittance_matrices:

Building the admittance matrices
================================

This operation occurs in the Compile() function of the Circuit object. This function compiles many other magnitudes and among them, the following matrices:

- Ybus: Complete admittance matrix. It is a sparse matrix of size n×n
- Yseries: Admittance matrix of the series elements. It contains no value comming from shunt elements or the shunt parts of the branch model. It is a sparse matrix of size n×n
- Yshunt: Admittance vector of the shunt elements and the shunt parts of the branch model. It is a vector of size n
- Yf: Admittance matrix of the banches with their from bus. It is a sparse matrix of size m×n
- Yt: Admittance matrix of the banches with their to bus. It is a sparse matrix of size m×n

Where n is the number of buses and m is the number of branches.

The relation between the admittance matrix and the series and shunt admittance matrices is the following:

.. math::

    Y_{bus} = Y_{series} + Y_{shunt}

The algorithmic logic to build the matrices in pseudo code is the following:

.. code::

    n = number of buses in the circuit
    m = number of branches in the circuit
    for i=0 to n:
        bus_shunt_admittance, bus_current, bus_power, bus_voltage = buses[i].get_YISV()
        Yshunt[i] = bus_shunt_admittance
    end

    for i=0 to m:
        f = get_bus_inde(branches[i].bus_from)
        t = get_bus_inde(branches[i].bus_to)
        // the matrices are modified by the branch object itself
        branches[i].apply_to(Ybus,Yseries,Yshunt,Yf,Yt,i,f,t)
    end

