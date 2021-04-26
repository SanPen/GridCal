
Change log
==========

This section describes the changes introduced at each Version.

\* Short releases indicate the fix of a critical bug.

\* Notice that some versions skip numbers. This is not an error,
this is because the stupid policy of pypi to not allow to correct packages.
Hence if something goes wrong, you need to re-upload with a new Version number.

Version 4.1.1
^^^^^^^^^^^^^^^

- Fixed per unit computation with the GUI dialogues.


Version 4.1.0
^^^^^^^^^^^^^^^

- Added coordinates and position input dialogue for the buses

- Added ability to set a branch rating profile from the snapshot, via a context menu option.

- Added time series clustering

- Added HDF file format .gch5

- Much faster read and write of .gridcal files due to the saving of the profiles in pandas "pickles"

- Fixed Areas not loading properly

- Fixed Time series indexing for discontinuous index.


Version 4.0.2
^^^^^^^^^^^^^^^

- Fixed xlrd dependency. It broke the profile import because it stopped supporting .xlsx.
  Switched to openpyxl.

- Fixed Wire call bug when not passing idtag.

- Added shunt voltage control.



Version 4.0.0 (multi-terminal DC Grids)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- General
    - Massive re-write of all the structures and the engine in order to have a more flexible
      approach to the devices and how the information is passed from the asset manager
      (the circuit) to the simulations. Hence the version jump attends to that massive effort.
    - Fixed transformer editor Sbase conversion.
    - Added HVDC line model.
    - Added VSC branch model.
    - Added DC line model.
    - Added tags to the sigma-plot.
    - Added Substation, Zone, Area and Country objects to group better the buses.


- GUI

    - Ability to select columns and rows when plotting the results
    - Added update check and command in the GUI about box.
    - Added a quite good random grid generator from the project SyntheticNetworks.
    - Added a bus viewer: It allows to visualize subsets of the grid.
      It is useful for very large grids where the complete schematic is cumbersome or slow.
    - Added check that converts the results into CDF.
    - Added check that converts the results into their absolute value.
    - Added schematic branch width based on the line flow.
    - Added button in the results to copy text data in numpy format.
    - Added column search in the results.

    - Revamp of the context menus.

    - Replaced how all the GUI messages are handled.

    - Improved the logger window, which now allows to save logs report.
    - Improved the transformer and line editors integrating the template selection.
    - Improved filtering (bool values are recognised now)

- I/O
    - Added better Json export file (v3.1 of the specification).
    - Improved the PSS/e Raw file import.
    - Implemented the ability to load several files to load a bunch of .xml CIM files together.


- Linear Analysis
    - Replaced the empirical PTDF/OTDF by the analytical PTDF/LODF which are several orders of magnitude faster.
    - Added linear contingency analysis time series
    - Added linear grouping based on PTDF + DBScan clustering.

- Power Flow
    - Improved the speed of the power flow process, by delaying the matrices and vector
      calculations until needed by any method.
    - Fixed the line search in Newton-Raphson, now it is truly non-divergent.
    - Removed the outer loop completely. Now the outer loop controls are performed inside the
      numerical methods that allow it (NR, LM, etc...) This is much faster.
    - Now the reactive power control only converts PQ->PV, and not the other way around. This renders into
      a more stable process.
    - Seamless AC-DC simulation:
        - Added the FUBM model at the numeric circuit level
        - Added FUBM version of the line-search Newton-Raphson method (without the super optimized jacobian for now)
        - Integrated it with the GUI.
        - The advanced controls such a transformer power set-points are simulated using the FUBM logic.

- Stochastic Power Flow
    - Merged Monte Carlo and Latin Hypercube in the same simulation driver.

- Continuation Power Flow
    - Added reactive power limits option for the generators.
    - Added overload stop criteria.
    - Added distributed slack.
    - Added back-tracking mechanism to the corrector step.
    - Now you can select to collapse a selection of nodes, from the GUI as well.
    - Now you can set the direction of the continuation negative so that you actually
      increase the generation. This allows the use of the CPF as an exploration tool.



Version 3.7.1
^^^^^^^^^^^^^^^^^^^^^

- Added Jacobian with numba optimization from Pandapower increasing Newton-Raphson performance by x20.
- Measuring the branch power instead of the current in the stochastic simulations.
- Fixes the problem with qtConsole by not displaying the console if the package crashes. Hopefully the QtConsole team
  will fix their issue.

Version 3.7.0 (HELM)
^^^^^^^^^^^^^^^^^^^^^

- Replaced the numerical circuit by two specialised objects: one for static power flow and another one for time series
  This allows to include specific circuit compilations for different studies such as harmonics ot dynamic studies
  without overcrowding the numerical circuit object with unused stuff.
- Greatly improved the time series flushing speed when saving.
- Improved the auto-link feature in the time series import.
- Added clustering to the time series.
- Added ability to not to draw the schematic. This speeds up operation with very large grids.
- The time series output size now adjust to the selected time interval.
- Now to drop a file does not automatically load the grid when another one is loaded.
- Replaced the previous HELM version by a working and competitive one thanks to Josep Fanals Batllori.
- Added the HELM-Sigma analysis tool.

Version 3.6.7
^^^^^^^^^^^^^^

- Fixed critical bug with the user gathering under windows.
- Improved the Analysis tool.

Version 3.6.6
^^^^^^^^^^^^^^

- Fixed PTDFTimeSeries timing.
- Connected loose parameters on the PTDFTimeSeries class.
- Fixed the Fast decoupled power flow algorithm.

Version 3.6.5
^^^^^^^^^^^^^^

- Added Sqlite save/open support.
- Added Grid append functionality.
- Added units in the results.
- Now all the results are displayed in real numbers instead of in complex numbers.
- Added an amazing functionality to allow model synchronization across several computers.


Version 3.6.4
^^^^^^^^^^^^^^

- Integrated better the PTDF into the GUI.
- Added VTDF calculations in the PTDF and PTDF time series.
- Added GIS as a visualization option.
- Improved the OPF formulation times.
- Improved the Jacobian-based power flow speeds by reducing the steps in the error computation.
- Fixed loading visualization in the schematic.


Version 3.6.3
^^^^^^^^^^^^^^

- Added equipment catalogue to the docs.
- Added tutorial section to the docs.
- Added simple dispatch.
- Refactored the device-bus connectivity matrices to avoid transpositions.
- Added function to relocate buses based on their peers.
- Added PTDF based time series.
- Fixed very important bug that neglected the sign of the power flows!

Version 3.6.2
^^^^^^^^^^^^^^

- Added logs record to the "export all" process.
- Added a console reset. This is needed when the console crashes.
- Improved the grid data expert analysis tool.
- Now the GUI elements are in a package *GridEditorWidget* instead of a single file.
  This improves the maintainability.
- Added ability to set OPF generation into the power flow, the load shedding is also subtracted.
- Fixed long standing bug related to MC and LHS having very small variation.
- Fixed bug with buses not creating their own profile
- Fixed bug with the run power flow interface


Version 3.6.1
^^^^^^^^^^^^^^

- Added N-1 and OTDF
- Now the plots are way faster
- Now the export results truly exports everything into a zip file with csv files inside.
- The top menus have been re-arranged.
- The multi-core test was moved into research.
- Added tap module to the power flow results.
- Fixed bug related to OPF results being multiplied by :math:`Sbase` twice.
- Fixed units displayed in the results plot.
- Fixed the results representation when single-node islands were ignored.

Version 3.6.0
^^^^^^^^^^^^^^

- Fixed csv profile input.
- Added similarity-based auto link in the profile import.
- Improved PSS/e import by improving the device naming.
- Refactored the power flow section, removing quite a lot of the
  existing complexity. Now there is only one power flow class which
  calls to power flow functions.
- Changed the multiprocess from multiple processes to a pool.
  Hopefully this will allow multi-core on MS Windows.
- Added a proper logger object.


Version 3.5.9
^^^^^^^^^^^^^^

- Added the ability to ignore single node islands
- Fixed voltage module in the LACPF algorithm: Now the PQ buses voltage is closer to NR.
- Improved the Newton-Raphson line search speed by roughly 200% by tuning the acceleration parameter.

Version 3.5.8
^^^^^^^^^^^^^^

- Fixed PTDF and added cancelling.
- Fixed Vbranch not being copied correctly in multi-island mode in the Time series.
- Redesigned the results tab: Now the data is the default view and the plot is optional. This allows
  a much better user interface experience since Matplotlib does not block the results when the grids are large.
- Added N-k simulation.
- Fixed PSS/e import branches; PSS/e does not account for the length in the impedance computation.
- Greatly improved the PSS/e file parser by using variable length lists.
- Implemented the distributed slack.
- Open by GUI file drop.
- Fixed bug: Now when many generators are at a node only one controls voltage.

Version 3.5.7
^^^^^^^^^^^^^^

- Fixed profile default-value initialization in automatic-load function.
- Added branch dynamic rating.


Version 3.5.6
^^^^^^^^^^^^^^

- Added thread for buses delete-and-reduce functionality.
- Moved the pulp solvers into individual files.
- Implemented the option to choose the linear algebra framework.
- Vastly improved DC power flow performance.


Version 3.5.5
^^^^^^^^^^^^^^

- Added generator technology property
- Refactored code to make it simpler:
    - The enum's behave like types and are able to parse text into types.
    - The objects editor is now agnostic of complex types, and so are the load and save functions.
- Added Power Transfer Distribution Factors (PTDF) analysis


Version 3.5.4
^^^^^^^^^^^^^^

- Fixed bug related to adding wires to the GUI.
- For some reason, `sdist` does not ship the right files to pypi, so changed to `bdist_wheel`
- Fixed code smells


Version 3.5.3
^^^^^^^^^^^^^^

- Added voltage angle in the power flow results and time series power flow results. About time!
- Removed warnings from the power flow driver. Now the warnings are stored in a log and displayed in the GUI.
- Fixed the rare bug of native open file dialogues not showing up. Native dialogues can be activated anytime via the
  "use_native_dialogues" flag in the GUI module.
- Fixed multi-island opf simulation in all the modes.
- Radically changed the way the file information is read. Now the function is much easier to maintain, so that changes
  in the objects should not affect the ability to read/write.
- Changed the way the overhead lines tower information is stored. Now should be more maintainable.

Version 3.5.2
^^^^^^^^^^^^^^

- Removed pulp dependency in the generator objects (forced a critical update)
- Added some icons in the GUI

Version 3.5.1
^^^^^^^^^^^^^^

- Simplified and unified the OPF interfaces.
- Added AC-liner OPF time series as a non-sequential algorithm.
- Added shadow prices to the non-sequential OPF.
- Added the handling of dispatchable non dispatchable generators to the OPF.
- Fixed bug with the OPF offset when starting at a index other than 0.
- Fixed bug with time grouping that repeated the last index.
- Fixed bug with the delegates setting for the boolean values


Version 3.5.0 (commemorating the 100 GitHub stars)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Added pulp as an embedded dependency, and updated its CBC solver with a custom compiled one from the latest sources.
- Fixed some bug related to the OPF storage and results display in non-sequential mode.

Version 3.4.2
^^^^^^^^^^^^^^

- Fixed branch saving code (hopefully forever)
- Fixed the loading of some properties that were missing.
- Fixed the non-sequential OPF.

Version 3.4.1
^^^^^^^^^^^^^^

- Added branch voltage and angle drops in the power flow and power flow time series simulations.
- Added cost profiles for the use in the OPF programs.
- Fixed critical bug when applying profile to snapshot.
- Fixed pySide related bug when converting dates.
- Fixed ui bug when setting values in the profiles manually.

Version 3.4.0
^^^^^^^^^^^^^^

- Now when highlighting the selection, the buses on the schematic are selected.
  This feature allows to move buses in bulk after any selection kind.
- Added feature to highlight buses based on any numeric property from the grid objects.
- Added "master" delete from the schematic.
  Now any selection of buses from the schematic can be deleted at once.

Version 3.3.9
^^^^^^^^^^^^^^

- Improved object filtering.
- Fixed critical bug involving the change to setuptools.

Version 3.3.7
^^^^^^^^^^^^^^

- Added filtering capabilities to the object browser.
- Added Bus reduction.
- Added bus highlight based on the object filtering.

Version 3.3.6
^^^^^^^^^^^^^^

- Continued to improved PSS/e .raw support.
- Fixed the bug caused by PySide2 with the excel sheet selection window.


Version 3.3.5
^^^^^^^^^^^^^^

- Greatly improved PSS/e .raw file import support.

Version 3.3.4
^^^^^^^^^^^^^^

- The tower names are displayed correctly now.

- Completely switched from PyQt5 to PySide2.

- Added support for PSS/e RAW file format Version 29.

- Overall bug fix.


Version 3.3.0
^^^^^^^^^^^^^^

- Now the branches and the buses have activation profiles. This allows to run time series
  where the topology changes. Only available for time series for the moment.

- The branches now allow to profile their temperature.
  This allows to change the resistance to explore heat effects.

- Added undo / redo to the profiles editor. This improves usability quite a bit.

- Added csv files into zip files as the GridCal default format. This allows to use the same logic
  as with the excel files but with much faster saving and loading times.
  Especially suited for large grids with large profiles.

- Added error logging for the power flow time series.

- Massive refactoring of the the files in the program structure,
  hoping to provide a more intuitive interface.

- Replace the internal profiles from Pandas DataFrames to numpy arrays.
  This makes the processing simpler and more robust.

- Added rating to cables.

- Changed the TransformerType inner property names to shorter ones.

- Plenty of bug fixes.

