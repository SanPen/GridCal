Gr  .. _distribution_grid_library:

Distribution Grid Library
=========================

This tutorial shows different ways and actions that you can do while using GridCal as a Python Library.
This mode has various advantages such as: more efficient modeling, modeling automation, and overall a more cutomizable experience.
The tutorial will give you the tools, to create models, run studies and visualize results.

Loading an Existing Model
-------------------------
If you have already created a model such as the 'Distribution Grid Model' or any .gridcal file you can load it in a Python Script the following way:

.. code-block:: python

    from GridCal.Engine import *

This is specially useful if you would like to create the grid using the GUI but run analysis, visualize results or pair it with other Python tools suchas NumPy or Pandas, etc.

.. code-block:: python

    from GridCal.Engine import *

**Note:** you can still change the grid within the script but this is meant just to load a finished script.


Creating a Model
----------------
In this section we will create the same 'Distribution Grid' from here_.

.. _here: https://gridcal.readthedocs.io/en/latest/tutorials/distribution_grid.html

Step 0: System Overview
^^^^^^^^^^^^^^^^^^^^^^^

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
