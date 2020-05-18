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

Note: A transformer will be created between HV Bus and Bus 2 when nominal voltage values are different.
Note: The name of an element may not change until you 'double click' the element on the diagram canvas after the change.

Step 2: Create a Lines of Different Lengths
-------------------------------------------

1. Create 3 more Buses (Bus 3, Bus 4 and Bus 5) and create a branch between them.

.. figure:: ../figures/tutorials/dg/threebusaddition.png
    :scale: 70 %

2. Select the branch between Bus 2 and Bus 3 and change its parameters to:

+------------+--------+
|   name     | Line 1 |
+------------+--------+
| length[km] |   5    |
+------------+--------+

3. Select the branch between Bus 3 and Bus 4 and change its parameters to:

+------------+--------+
|   name     | Line 2 |
+------------+--------+
| length[km] |   3    |
+------------+--------+

4. Select the branch between Bus 4 and Bus 5 and change its parameters to:

+------------+--------+
|   name     | Line 3 |
+------------+--------+
| length[km] |   7    |
+------------+--------+


Note: Element placing can be changed by 'clicking' the square on the right hand side of a bus.

Step 3: Add more Lines and Buses
--------------------------------

1. Add Bus 6 to the right of Bus 2.
2. Add Bus 7 to the right of Bus 3.
3. Add Bus 8 and Bus 10 to the left of Bus 4.
4. Add Bus 9 and Bus 11 to the left of Bus 5.

.. figure:: ../figures/tutorials/dg/morebuses.png
    :scale: 70 %

5. Select the branch between Bus 2 and Bus 6 and change its parameters to:

+------------+--------+
|   name     | Line 4 |
+------------+--------+
| length[km] |   2    |
+------------+--------+

5. Select the branch between Bus 3 and Bus 7 and change its parameters to:

+------------+--------+
|   name     | Line 5 |
+------------+--------+
| length[km] |   1.6  |
+------------+--------+

6. Select the branch between Bus 4 and Bus 8 and change its parameters to:

+------------+--------+
|   name     | Line 7 |
+------------+--------+
| length[km] |   1.5  |
+------------+--------+

7. Select the branch between Bus 5 and Bus 9 and change its parameters to:

+------------+--------+
|   name     | Line 8 |
+------------+--------+
| length[km] |    2   |
+------------+--------+

.. figure:: ../figures/tutorials/dg/morebuseslines.png
    :scale: 70 %

Step 4: Create Loads
--------------------