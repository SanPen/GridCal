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

1. Select Bus 10 and change parameters to:

+----------+----------+
|   name   | House 3  |
+----------+----------+
| Vnom[kV] |   0.4    |
+----------+----------+

2. Create a line between Bus 8 and House 3 (a transformer will be created). Rename it to 'TR House 3'.

3. Select Bus 11 and change parameters to:

+----------+----------+
|   name   | House 4  |
+----------+----------+
| Vnom[kV] |   0.4    |
+----------+----------+

4. Create a line between Bus 9 and House 4 (a transformer will be created). Rename it to 'TR House 4'.

5. Right 'click' on House 3 and select 'Add Load'.

6. Right 'click' on House 4 and select 'Add Load'.

.. figure:: ../figures/tutorials/dg/loads.png
    :scale: 70 %

Step 5: Create House 1 and House 2
----------------------------------

1. Create load House 1: Create a new bus and name it 'House 1' to the right of Bus 6, and a transformer in the line between Bus 6 and House 1. The parameters are the following:

+----------+----------+
|   name   | House 1  |
+----------+----------+
| Vnom[kV] |   0.4    |
+----------+----------+

2. Create load House 2: Create a new bus and name it 'House 2' to the right of Bus 7, and a transformer in the line between Bus 7 and House 2. The parameters are the following:

+----------+----------+
|   name   | House 2  |
+----------+----------+
| Vnom[kV] |   0.4    |
+----------+----------+

The full system topoly looks like:

.. figure:: ../figures/tutorials/dg/fourhouses.png
    :scale: 70 %

Note: do not forget to add the load after you rename the House buses.

Step 6: Defining the Main Transformer
-------------------------------------

In order to define the type of transformer a catalogue is available within the GridCal repository.

This transformer is the transformer between HV Bus and Bus 2. The transformer is: 25 MV 20/10 kV.

1. Access the catalogue (Excel file). It can be found in the repository at Gridcal/Grids_and_profiles/grids/equipment and select 'equipment.ods'.

2. Select the 'Transformers' sheet.

3. Remove all filters on the 'Rate (MVA)' column by pressing on the downward arrow.

.. figure:: ../figures/tutorials/dg/downtriangle.png
    :scale: 70 %

4. Select the '20 kV' filter on the 'HV (kV)' column using the downward arrow.

4. Select the '10 kV' filter on the 'LV (kV)' column using the downward arrow.


6. The parameters of the transformer are:

+--------------------+------------------+
|        name        | 25 MVA 20/10 kV  |
+--------------------+------------------+
|     Rate[MVA]      |       25         |
+--------------------+------------------+
|   Frequency[Hz]    |       50         |
+--------------------+------------------+
|       HV[kV]       |       20         |
+--------------------+------------------+
|       LV[kV]       |        10        |
+--------------------+------------------+
|  Copper Losses[kW] |      102.76      |
+--------------------+------------------+
| No Load Losses[kW] |      10.96       |
+--------------------+------------------+
| No Load Current[%] |       0.1        |
+--------------------+------------------+
| V Short Circuit[%] |      10.3        |
+--------------------+------------------+
| HV Vector Group    |        YN        |
+--------------------+------------------+
|   LV Vector Group  |         D        |
+--------------------+------------------+
|   Phase Shift      |       5          |
+--------------------+------------------+

7. Double click on the transformer between HV Bus and Bus 2 and enter the following parameters (based on the model selected):

+--------+--------+
|   Sn   | 25     |
+--------+--------+
|  Pcu   | 102.76 |
+--------+--------+
|   Pfe  |  10.96 |
+--------+--------+
|   lo   | 0.1    |
+--------+--------+
|    Vsc | 10.3   |
+--------+--------+

8. Once the parameters are placed, right click and select 'Add to catalogue'. This way the branch p.u. values are calculated from the template values.

Note: In the new GridCal version, a transformer can be defined by just right clicking on the desired transformer and selecting the type from the drop down menu.

Note: All of the element types can be found under the 'Types catalogue' tab after clicking on the desired element, then clock 'Load Values' to change the parameters.

Step 7: Defining Load Transformers
----------------------------------

The transformers used for the 4 loads (houses) a 10 to 0.4 kV transformer will be used. The name is a '0.016 MVA 10/0.4 kV ET 16/23 SGB'.

1. Using the same catalogue find the transformer and do this for the transformer between Bus 6 and House 1.

2. The parameters of the transformer are:

+--------------------+-----------------------------------+
|        name        | 0.016 MVA 10/0.4 kV ET 16/23 SGB  |
+--------------------+-----------------------------------+
|     Rate[MVA]      |                       0.016       |
+--------------------+-----------------------------------+
|   Frequency[Hz]    |                         50        |
+--------------------+-----------------------------------+
|       HV[kV]       |                         10        |
+--------------------+-----------------------------------+
|       LV[kV]       |                        0.4        |
+--------------------+-----------------------------------+
|  Copper Losses[kW] |                            0.45   |
+--------------------+-----------------------------------+
| No Load Losses[kW] |                         0.11      |
+--------------------+-----------------------------------+
| No Load Current[%] |                       0.68751     |
+--------------------+-----------------------------------+
| V Short Circuit[%] |                          3.75     |
+--------------------+-----------------------------------+
| HV Vector Group    |                            Y      |
+--------------------+-----------------------------------+
|   LV Vector Group  |                            ZN     |
+--------------------+-----------------------------------+
|   Phase Shift      |                         5         |
+--------------------+-----------------------------------+

3. Fill these values out for the pop up menu:

+--------+---------+
|   Sn   |  0.016  |
+--------+---------+
|  Pcu   | 0.45    |
+--------+---------+
|   Pfe  |  0.11   |
+--------+---------+
|   lo   |0.687510 |
+--------+---------+
|    Vsc |3.75     |
+--------+---------+

4. Right click on the transformer and select 'Add to catalogue' this will create a template for quick add.

5. Rename the transformer to 'TR house 1'.

6. On the lower tabs select 'Types catalogue'.

.. figure:: ../figures/tutorials/dg/typescatalogue.png
    :scale: 70 %

7. Select the transformer that has the characteristics of the 10 to 0.4 kV transformer and rename it to 'House trafo'. Now you have defined a transformer type that can be added to many transformers.

Note: In the new GridCal version, a transformer can be defined by just right clicking on the desired transformer and selecting the type from the drop down menu.

Step 7: Defining Load Transformer
---------------------------------

Now that 'House trafo' has been created, other transformers can be set to the same type.

1. In the 'Schematic' tab change the name of the other load transformers to their respective load (i.e. House 3 transformer rename to 'TR house 3').

2. Double click on the transformer

3. Click 'Load Values' to set the parameters.

4. Repeat for all desired transformers: TR house 3, TR house 4, TR house 2.

Note: this can be done with all elements either to preloaded models or models you create.


Step 8: Defining Load Transformer
---------------------------------