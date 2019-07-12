
Change log
==========

This section describes the changes introduced at each version.

\* Short releases indicate the fix of a critical bug.

\* Notice that some versions skip numbers. This is not an error,
this is because the stupid policy of pypi to not allow to correct packages.
Hence if something goes wrong, you need to re-upload with a new version number.

version 3.4.2
_____________

- Fixed branch saving code (hopefully forever)
- Fixed the loading of some properties that were missing.
- Fixed the non-sequential OPF.

version 3.4.1
_____________

- Added branch voltage and angle drops in the power flow and power flow time series simulations.
- Added cost profiles for the use in the OPF programs.
- Fixed critical bug when applying profile to snapshot.
- Fixed pySide related bug when converting dates.
- Fixed ui bug when setting values in the profiles manually.

version 3.4.0
_____________

- Now when highlighting the selection, the buses on the schematic are selected.
  This feature allows to move buses in bulk after any selection kind.
- Added feature to highlight buses based on any numeric property from the grid objects.
- Added "master" delete from the schematic.
  Now any selection of buses from the schematic can be deleted at once.

version 3.3.9
_____________

- Improved object filtering.
- Fixed critical bug involving the change to setuptools.

version 3.3.7
_____________

- Added filtering capabilities to the object browser.
- Added Bus reduction.
- Added bus highlight based on the object filtering.

version 3.3.6
_____________

- Continued to improved PSS/e .raw support.
- Fixed the bug caused by PySide2 with the excel sheet selection window.


version 3.3.5
_____________

- Greatly improved PSS/e .raw file import support.

version 3.3.4
_____________

- The tower names are displayed correctly now.

- Completely switched from PyQt5 to PySide2.

- Added support for PSS/e RAW file format version 29.

- Overall bug fix.


version 3.3.0
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

