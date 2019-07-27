
Change log
==========

This section describes the changes introduced at each Version.

\* Short releases indicate the fix of a critical bug.

\* Notice that some versions skip numbers. This is not an error,
this is because the stupid policy of pypi to not allow to correct packages.
Hence if something goes wrong, you need to re-upload with a new Version number.

Version 3.5.1
_____________

- Simplified and unified the OPF interfaces.
- Added AC-liner OPF time series as a non-sequential algorithm.
- Added shadow prices to the non-sequential OPF.
- Fixed bug with the OPF offset when starting at a index other than 0.
- Fixed bug with time grouping that repeated the last index.


Version 3.5.0 (commemorating the 100 GitHub stars)
__________________________________________________

- Added pulp as an embedded dependency, and updated its CBC solver with a custom compiled one from the latest sources.
- Fixed some bug related to the OPF storage and results display in non-sequential mode.

Version 3.4.2
_____________

- Fixed branch saving code (hopefully forever)
- Fixed the loading of some properties that were missing.
- Fixed the non-sequential OPF.

Version 3.4.1
_____________

- Added branch voltage and angle drops in the power flow and power flow time series simulations.
- Added cost profiles for the use in the OPF programs.
- Fixed critical bug when applying profile to snapshot.
- Fixed pySide related bug when converting dates.
- Fixed ui bug when setting values in the profiles manually.

Version 3.4.0
_____________

- Now when highlighting the selection, the buses on the schematic are selected.
  This feature allows to move buses in bulk after any selection kind.
- Added feature to highlight buses based on any numeric property from the grid objects.
- Added "master" delete from the schematic.
  Now any selection of buses from the schematic can be deleted at once.

Version 3.3.9
_____________

- Improved object filtering.
- Fixed critical bug involving the change to setuptools.

Version 3.3.7
_____________

- Added filtering capabilities to the object browser.
- Added Bus reduction.
- Added bus highlight based on the object filtering.

Version 3.3.6
_____________

- Continued to improved PSS/e .raw support.
- Fixed the bug caused by PySide2 with the excel sheet selection window.


Version 3.3.5
_____________

- Greatly improved PSS/e .raw file import support.

Version 3.3.4
_____________

- The tower names are displayed correctly now.

- Completely switched from PyQt5 to PySide2.

- Added support for PSS/e RAW file format Version 29.

- Overall bug fix.


Version 3.3.0
_____________

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

