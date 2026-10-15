-- This Source Code Form is subject to the terms of the Mozilla Public
-- License, v. 2.0. If a copy of the MPL was not distributed with this
-- file, You can obtain one at https://mozilla.org/MPL/2.0/.
-- SPDX-License-Identifier: MPL-2.0

--- Stop the driver when an OMSimulator API call fails.
-- @param status OMSimulator status returned by the API call.
-- @param operation Human-readable operation name.
local function require_ok(status, operation)
  if status == oms_status_ok then
    return
  else
    error(operation .. " failed with OMSimulator status " .. tostring(status))
  end
end

--- Write one finite canonical SMIB sample.
-- @param output_file Open output file owned by this driver.
-- @param sample_index Zero-based sample index.
-- @param time_value Simulation time in seconds.
local function write_sample(output_file, sample_index, time_value)
  local angle, angle_status = oms_getReal("vg.root.plant.angle")
  local speed, speed_status = oms_getReal("vg.root.plant.speed")
  local electrical_power, power_status = oms_getReal(
    "vg.root.plant.electricalPower"
  )
  local effective_reactance, reactance_status = oms_getReal(
    "vg.root.plant.effectiveReactance"
  )
  require_ok(angle_status, "oms_getReal angle")
  require_ok(speed_status, "oms_getReal speed")
  require_ok(power_status, "oms_getReal electricalPower")
  require_ok(reactance_status, "oms_getReal effectiveReactance")

  local values_are_finite = (
    angle == angle
    and speed == speed
    and electrical_power == electrical_power
    and effective_reactance == effective_reactance
    and math.abs(angle) ~= math.huge
    and math.abs(speed) ~= math.huge
    and math.abs(electrical_power) ~= math.huge
    and math.abs(effective_reactance) ~= math.huge
  )
  if values_are_finite then
    output_file:write(string.format(
      "%d,%.17e,%.17e,%.17e,%.17e,%.17e\n",
      sample_index,
      time_value,
      angle,
      speed,
      electrical_power,
      effective_reactance
    ))
  else
    error("OMSimulator produced a nonfinite SMIB sample")
  end
end

-- Build one weakly coupled Co-Simulation system around the exact staged FMU.
require_ok(oms_newModel("vg"), "oms_newModel")
require_ok(oms_addSystem("vg.root", oms_system_wc), "oms_addSystem")
require_ok(oms_addSubModel("vg.root.plant", "model.fmu"), "oms_addSubModel")
require_ok(oms_setSolver("vg.root", oms_solver_wc_ma), "oms_setSolver")
require_ok(oms_setFixedStepSize("vg.root", 0.000125), "oms_setFixedStepSize")
require_ok(oms_setResultFile("vg", "", 0), "oms_setResultFile")
require_ok(oms_instantiate("vg"), "oms_instantiate")
require_ok(oms_initialize("vg"), "oms_initialize")

local output_file, output_error = io.open("smib_omsimulator_trace.csv", "wb")
if output_file == nil then
  error("Unable to open SMIB output: " .. tostring(output_error))
else
  output_file:write(
    "sample_index,time_seconds,angle_rad,speed_pu,electrical_power_pu,effective_reactance_pu\n"
  )
end

-- Advance every fine communication point and retain every sixteenth result.
write_sample(output_file, 0, 0.0)
for communication_index = 1, 32000 do
  local time_value = communication_index * 0.000125
  require_ok(oms_stepUntil("vg", time_value), "oms_stepUntil")
  if communication_index % 16 == 0 then
    local sample_index = math.floor(communication_index / 16)
    write_sample(output_file, sample_index, time_value)
  else
    -- Intermediate communication points are intentionally not retained.
  end
end

output_file:close()
require_ok(oms_terminate("vg"), "oms_terminate")
require_ok(oms_delete("vg"), "oms_delete")
