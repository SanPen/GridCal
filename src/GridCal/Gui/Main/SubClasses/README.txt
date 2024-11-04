# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0



Since version 5.0.0 GridCal's main GUI class
was split in many other classes that inherit
from each other linearly. This was done to
simplify the massive original class.

The subclasses inheritance order is:

BaseMainGui
ServerMain
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