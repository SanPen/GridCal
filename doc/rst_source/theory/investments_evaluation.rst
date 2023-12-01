Investments evaluation
_______________________________________
Documentar grid de pruebas

Objective function

.. math::
    f = \sum overaloadcost + \sum voltagecost + \sum losses +\sum capex+ \sum opex
Añadir pruebas diferentes weight CAPEX
Añadir figures


.. figure:: ../figures/investments/Figure_1_w_capex-e-6.png
    :alt: Results1
    :scale: 50 %


.. math::
    f = w_1\frac{\sum overaloadcost}{||overloadcost||} + w_2\frac{\sum voltagecost}{||overvoltagecost||}
    + w_3\frac{\sum losses}{||losses||} + w_4\frac{\sum capex}{||capex||} + w_5\frac{\sum opex}{||opex||}