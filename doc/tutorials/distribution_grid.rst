.. _distribution_grid:

Distribution Grid
==================
This tutorial shows a step by step guide on how to build distribution grid system that contains: 13 Buses, 4 Transformers, 4 Loads. The tutorial shows how to create a grid using time profiles and device templates. The tutorial also contains:

- Easy drag and drop creation of components.
- Transformer type creation.
- Overhead lines creation.
- Templates for transformers and overhead lines.
- Import of profiles into the loads.
- Set s power flow snapshot from the profiles.
- Execution of power flow.
- Execution of power flow time series.
- Automatic precision adjustment.
- Results visualization.
- Live results visualization (grid colouring).

A video tutorial can be found here_.

.. _here: https://www.youtube.com/watch?v=Yx3zRYRbe04&t=404s

Note: this tutorial was made with GridCal v 4.0.0

Step 0: System Overview
-----------------------
The system grid is supposed to look like the figure below.

.. figure:: ../figures/tutorials/dg/overview.png
    :scale: 70 %

The parameters of the system are:

Buses:

Loads:

Lines:

Transformers:



Solution file of the grid system can be found in _GitHub.

.. _GitHub:



Step 1: Create a Transformer
----------------------------
Open GridCal:

1. 'Drag and drop' 2 'Bus' element to the diagram canvas:

.. figure:: ../figures/tutorials/dg/busaddition.png
    :scale: 70 %

2. Select (double 'click') Bus 0 and change the parameters (on the left side pane):

+----------+--------+
|   name   | HV Bus |
+----------+--------+
| Vnom[kV] |   20   |
+----------+--------+

3. Select (double 'click') Bus 1 and change the parameters (on the left side pane):

+----------+--------+
|   name   | Bus 2  |
+----------+--------+
| Vnom[kV] |   10   |
+----------+--------+

4. Hover over either bus element, 'click and drag' (when there is a cross) to the other bus to create a branch.

.. figure:: ../figures/tutorials/dg/transformer.png
    :scale: 70 %

A transformer will be created between HV Bus and Bus 2.

Step 2: Create a Lines of Different Lengths
-------------------------------------------