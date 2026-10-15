-- This Source Code Form is subject to the terms of the Mozilla Public
-- License, v. 2.0. If a copy of the MPL was not distributed with this
-- file, You can obtain one at https://mozilla.org/MPL/2.0/.
-- SPDX-License-Identifier: MPL-2.0

--- Stop the driver when an OMSimulator API call does not succeed.
-- @param status OMSimulator status returned by the API call.
-- @param operation Human-readable operation name for diagnostics.
local function require_ok(status, operation)
  if status == oms_status_ok then
    return
  else
    error(operation .. " failed with OMSimulator status " .. tostring(status))
  end
end

--- Convert the retained mode text to the exact OMSimulator configuration.
-- @param mode_text Canonical CoSimulation or ModelExchange string.
-- @return OMSimulator system type and solver enumeration values.
local function read_mode(mode_text)
  if mode_text == "CoSimulation" then
    return oms_system_wc, oms_solver_wc_ma
  elseif mode_text == "ModelExchange" then
    return oms_system_sc, oms_solver_sc_cvode
  else
    error("Unsupported FMI mode " .. tostring(mode_text))
  end
end

--- Parse and validate the complete retained input contract.
-- @param input_path Relative path to the bounded input CSV.
-- @return Mode text plus canonical index, time and voltage arrays.
local function read_input_rows(input_path)
  local input_file, open_error = io.open(input_path, "rb")
  if input_file == nil then
    error("Unable to open OMSimulator input: " .. tostring(open_error))
  else
  end

  local content = input_file:read("*all")
  input_file:close()
  if content == nil then
    error("Unable to read OMSimulator input")
  elseif #content > 65536 then
    error("OMSimulator input exceeds 64 KiB")
  elseif string.sub(content, -1) ~= "\n" then
    error("OMSimulator input lacks the final LF")
  elseif string.find(content, "\r", 1, true) ~= nil then
    error("OMSimulator input contains CR")
  elseif string.find(content, '"', 1, true) ~= nil then
    error("OMSimulator input contains quoting")
  elseif string.find(content, "\n\n", 1, true) ~= nil then
    error("OMSimulator input contains a blank row")
  else
  end

  local header = "sample_index,mode,time_seconds,voltage_magnitude_pu\n"
  if string.sub(content, 1, #header) == header then
  else
    error("OMSimulator input header is invalid")
  end

  local indices = {}
  local times = {}
  local voltages = {}
  local retained_mode = nil
  local body = string.sub(content, #header + 1)
  local row_number = 0
  for line in string.gmatch(body, "([^\n]+)\n") do
    local index_text, mode_text, time_text, voltage_text = string.match(
      line,
      "^([^,]+),([^,]+),([^,]+),([^,]+)$"
    )
    if index_text == nil then
      error("OMSimulator input row has an invalid column count")
    else
    end

    local index_value = tonumber(index_text)
    local time_value = tonumber(time_text)
    local voltage_value = tonumber(voltage_text)
    if index_value == nil or time_value == nil or voltage_value == nil then
      error("OMSimulator input row contains a nonnumeric value")
    elseif index_text ~= tostring(row_number) or index_value ~= row_number then
      error("OMSimulator input sample index is not canonical")
    elseif time_text ~= string.format("%.17e", time_value) then
      error("OMSimulator input time is not canonical")
    elseif voltage_text ~= string.format("%.17e", voltage_value) then
      error("OMSimulator input voltage is not canonical")
    elseif time_value ~= time_value or math.abs(time_value) == math.huge then
      error("OMSimulator input time is not finite")
    elseif voltage_value ~= voltage_value or math.abs(voltage_value) == math.huge then
      error("OMSimulator input voltage is not finite")
    elseif math.abs(time_value - row_number * 0.001) > 1e-12 then
      error("OMSimulator input time lattice is invalid")
    else
    end

    if retained_mode == nil then
      retained_mode = mode_text
    elseif retained_mode == mode_text then
    else
      error("OMSimulator input mode changes between rows")
    end
    indices[row_number + 1] = index_value
    times[row_number + 1] = time_value
    voltages[row_number + 1] = voltage_value
    row_number = row_number + 1
  end
  if row_number == 301 and retained_mode ~= nil then
    return retained_mode, indices, times, voltages
  else
    error("OMSimulator input must contain exactly 301 data rows")
  end
end

--- Write one canonical raw-evidence sample.
-- @param output_file Open output file owned by this driver.
-- @param sample_index Zero-based canonical sample index.
-- @param mode_text Canonical FMI interface mode.
-- @param time_value Sample time in seconds.
-- @param voltage_value Echoed FMU voltage input in p.u.
-- @param active_power FMU active-power output in p.u.
-- @param reactive_power FMU reactive-power output in p.u.
local function write_sample(
  output_file,
  sample_index,
  mode_text,
  time_value,
  voltage_value,
  active_power,
  reactive_power
)
  local values_are_finite = (
    time_value == time_value
    and voltage_value == voltage_value
    and active_power == active_power
    and reactive_power == reactive_power
    and math.abs(time_value) ~= math.huge
    and math.abs(voltage_value) ~= math.huge
    and math.abs(active_power) ~= math.huge
    and math.abs(reactive_power) ~= math.huge
  )
  if values_are_finite then
    output_file:write(string.format(
      "%d,%s,%.17e,%.17e,%.17e,%.17e\n",
      sample_index,
      mode_text,
      time_value,
      voltage_value,
      active_power,
      reactive_power
    ))
  else
    error("OMSimulator produced a nonfinite sample")
  end
end

-- Read the complete input before constructing the runtime model so malformed
-- evidence cannot trigger partial native execution.
local mode_text, sample_indices, sample_times, voltage_inputs = read_input_rows(
  "omsimulator_input.csv"
)
local system_type, solver_type = read_mode(mode_text)

-- Construct and configure one model with mode-specific, explicitly checked
-- solver settings. The native recorder is disabled because the driver owns the
-- normative 301-row output lattice.
require_ok(oms_newModel("vg"), "oms_newModel")
require_ok(oms_addSystem("vg.root", system_type), "oms_addSystem")
require_ok(oms_addSubModel("vg.root.device", "model.fmu"), "oms_addSubModel")
require_ok(oms_setSolver("vg.root", solver_type), "oms_setSolver")
require_ok(oms_setResultFile("vg", "", 0), "oms_setResultFile")
if mode_text == "CoSimulation" then
  require_ok(oms_setFixedStepSize("vg.root", 0.001), "oms_setFixedStepSize")
elseif mode_text == "ModelExchange" then
  require_ok(oms_setTolerance("vg.root", 1e-10, 1e-10), "oms_setTolerance")
else
  error("Unsupported mode after validation")
end
require_ok(oms_instantiate("vg"), "oms_instantiate")
require_ok(oms_setReal("vg.root.device.u", voltage_inputs[1]), "oms_setReal u[0]")
require_ok(oms_initialize("vg"), "oms_initialize")

local output_file, output_error = io.open("omsimulator_output.csv", "wb")
if output_file == nil then
  error("Unable to open OMSimulator output: " .. tostring(output_error))
else
  output_file:write(
    "sample_index,mode,time_seconds,voltage_magnitude_pu,active_power_pu,reactive_power_pu\n"
  )
end

-- Retain the initialized row before any advance. Subsequent rows advance with
-- the previous input, apply the boundary value, and then sample the algebraic
-- outputs on the prescribed side of the event.
local voltage_value, voltage_status = oms_getReal("vg.root.device.u")
require_ok(voltage_status, "oms_getReal u[0]")
local active_power, active_status = oms_getReal("vg.root.device.p_out")
require_ok(active_status, "oms_getReal p_out[0]")
local reactive_power, reactive_status = oms_getReal("vg.root.device.q_out")
require_ok(reactive_status, "oms_getReal q_out[0]")
write_sample(
  output_file,
  sample_indices[1],
  mode_text,
  sample_times[1],
  voltage_value,
  active_power,
  reactive_power
)

for row_index = 2, 301 do
  require_ok(oms_stepUntil("vg", sample_times[row_index]), "oms_stepUntil")
  require_ok(
    oms_setReal("vg.root.device.u", voltage_inputs[row_index]),
    "oms_setReal u"
  )
  voltage_value, voltage_status = oms_getReal("vg.root.device.u")
  require_ok(voltage_status, "oms_getReal u")
  active_power, active_status = oms_getReal("vg.root.device.p_out")
  require_ok(active_status, "oms_getReal p_out")
  reactive_power, reactive_status = oms_getReal("vg.root.device.q_out")
  require_ok(reactive_status, "oms_getReal q_out")
  write_sample(
    output_file,
    sample_indices[row_index],
    mode_text,
    sample_times[row_index],
    voltage_value,
    active_power,
    reactive_power
  )
end

output_file:close()
require_ok(oms_terminate("vg"), "oms_terminate")
require_ok(oms_delete("vg"), "oms_delete")
