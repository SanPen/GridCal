Gr  .. _distribution_grid_library:

Distribution Grid Library
=========================

In this section we will create the same 'Distribution Grid' from here_.

.. _here: https://gridcal.readthedocs.io/en/latest/tutorials/distribution_grid.html

However, we will do this using using GridCal as a Python Library.

Step 0: System Overview
^^^^^^^^^^^^^^^^^^^^^^^

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

The system grid is supposed to look like the figure below.

.. figure:: ../figures/tutorials/dg/overview.png
    :scale: 50%

The system featurese:

- 9 Buses.
- 5 Transformers.
- 4 Loads.
- 7 Lines.

Solution file of the grid system can be found in _GitHub.

.. _GitHub: https://github.com/SanPen/GridCal/blob/devel/Grids_and_profiles/grids/Some%20distribution%20grid%20(Video).gridcal

Step 0: Import GridCal and create model
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from GridCal.Engine import *
    grid = MultiCircuit()


Step 1: Create a Transfomer
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Step 2: Create Lines of Different Lengths
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Step 3: Add More Lines and Buses
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Step 4: Create Loads
^^^^^^^^^^^^^^^^^^^^

Step 5: Create House 1 and House 2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Step 6: Defining the Main Transformer
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Step 7: Defining Load Transformers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Step 8: Defining Other Transformers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Step 9: Defining Wires and Overhead Lines
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Step 10: Importing Load Profiles
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^



Entire Script
-------------

.. code-block:: python

    from GridCal.Engine import *
    grid = MultiCircuit()