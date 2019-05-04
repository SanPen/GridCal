
Change log
==========

version 3.3.0
_____________

- Now the branches and the buses have activation profiles. This allows to run time series
  where the topology changes. Only available for time series for the moment.

- The branches now allow to profile their temperature. This allows to change the resistance to explore heat effects.

- Added undo / redo to the profiles editor. This improves usability quite a bit.

- Added csv files into zip files as the GridCal default format. This allows to use the same logic
  as with the excel files but with much faster saving and loading times. Especially suited for
  large grids with large profiles.

- Massive refactoring of the the files in the program structure, hoping to provide a more intuitive interface.

- Replace the internal profiles from Pandas DataFrames to numpy arrays.
  This makes the processing simpler and more robust.

- Added rating to cables

- Plenty of bug fixes.

