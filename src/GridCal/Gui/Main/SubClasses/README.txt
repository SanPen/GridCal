Since version 5.0.0 GridCal's main GUI class
was split in many other classes that inherit
from each other linearly. This was done to
simplify the massive original class.

The subclasses inheritance order is:

BaseMainGui
CompiledArraysMain
DiagramsMain
ObjectsTableMain
TimeEventsMain
SimulationsMain
ResultsMain
ConfigurationMain
IoMain
ScriptingMain
MainGUI