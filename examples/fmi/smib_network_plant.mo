// This Source Code Form is subject to the terms of the Mozilla Public
// License, v. 2.0. If a copy of the MPL was not distributed with this
// file, You can obtain one at https://mozilla.org/MPL/2.0/.
// SPDX-License-Identifier: MPL-2.0

model VeraGridSmibNetworkPlant
  "Reduced single-machine infinite-bus benchmark with fault clearing"
  parameter Real inertia = 5.0 "Machine inertia constant in seconds";
  parameter Real damping = 1.0 "Per-unit damping coefficient";
  parameter Real mechanicalPower = 0.8 "Mechanical input power in p.u.";
  parameter Real internalVoltage = 1.1 "Internal machine voltage in p.u.";
  parameter Real infiniteBusVoltage = 1.0 "Infinite-bus voltage in p.u.";
  parameter Real preFaultReactance = 0.6 "Healthy transfer reactance in p.u.";
  parameter Real faultReactance = 1.2 "Faulted transfer reactance in p.u.";
  parameter Real faultStart = 1.001 "Fault application time in seconds";
  parameter Real faultEnd = 1.151 "Fault clearing time in seconds";
  parameter Real synchronousAngularFrequency = 314.1592653589793
    "Synchronous angular frequency in rad/s";
  output Real angle(
    start = 0.45155325894532272,
    fixed = true
  ) "Rotor electrical angle in radians";
  output Real speed(
    start = 1.0,
    fixed = true
  ) "Rotor speed in p.u.";
  output Real electricalPower "Transferred electrical power in p.u.";
  output Real effectiveReactance "Active network reactance in p.u.";
equation
  // The piecewise network reactance creates distinct fault-on and fault-clear
  // time events while keeping one autonomous physical source for every tool.
  effectiveReactance = if time < faultStart then preFaultReactance
    else if time < faultEnd then faultReactance else preFaultReactance;
  electricalPower = internalVoltage * infiniteBusVoltage
    * sin(angle) / effectiveReactance;

  // The classical swing equations provide non-zero derivatives after the
  // network disturbance and return toward the declared operating point.
  der(angle) = synchronousAngularFrequency * (speed - 1.0);
  der(speed) = (
    mechanicalPower - electricalPower - damping * (speed - 1.0)
  ) / (2.0 * inertia);
end VeraGridSmibNetworkPlant;
