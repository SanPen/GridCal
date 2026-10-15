# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# Execute the fixed two-FMU FMI.jl Co-Simulation benchmark.
using FMI
using Printf
using SHA


"""Authenticate one immutable input before native loading."""
function verify_input(path::String, expected_sha256::String)::Nothing
    if isfile(path) && !islink(path)
        actual_sha256::String = bytes2hex(sha256(read(path)))
        if actual_sha256 == expected_sha256
            return nothing
        else
            error("Input SHA-256 differs from the authenticated value: $(path)")
        end
    else
        error("Authenticated input is absent or unsafe: $(path)")
    end
end


"""Read one named Real scalar through the FMI.jl low-level API."""
function read_real(component::FMI.FMU2Component, name::String)::Float64
    return Float64(fmi2GetReal(component, name))
end


"""Write the canonical full-precision trajectory without a table dependency."""
function write_trace(path::String, trace::Matrix{Float64})::Nothing
    if !ispath(path)
        output::IOStream = open(path, "w")
        try
            println(
                output,
                "time,{controller}.controller.MECH_CONTROL," *
                "{controller}.controller.SPEED,{plant}.plant.ANGLE," *
                "{plant}.plant.MECH_CONTROL,{plant}.plant.PELEC," *
                "{plant}.plant.SPEED,{plant}.plant.X_EFFECTIVE",
            )
            row_index::Int = 1
            while row_index <= size(trace, 1)
                @printf(output, "%.17g", trace[row_index, 1])
                column_index::Int = 2
                while column_index <= size(trace, 2)
                    @printf(output, ",%.17g", trace[row_index, column_index])
                    column_index += 1
                end
                println(output)
                row_index += 1
            end
        finally
            close(output)
        end
        return nothing
    else
        error("Refusing to overwrite FMI.jl output: $(path)")
    end
end


"""Run the explicit delayed-feedback composition on the exact time lattice."""
function execute_composition(
    plant_path::String,
    governor_path::String,
    output_path::String,
)::Nothing
    step_size::Float64 = 0.002
    step_count::Int = 2000
    row_count::Int = step_count + 1
    trace::Matrix{Float64} = Matrix{Float64}(undef, row_count, 8)
    plant_fmu::FMI.FMU2 = loadFMU(plant_path)
    governor_fmu::FMI.FMU2 = loadFMU(governor_path)
    plant::Union{Nothing,FMI.FMU2Component} = nothing
    governor::Union{Nothing,FMI.FMU2Component} = nothing
    try
        # Each FMU owns its solver; the coordinator exchanges accepted outputs
        # only at communication boundaries, matching the delayed OSP topology.
        plant = fmi2Instantiate!(plant_fmu; type = fmi2TypeCoSimulation)
        governor = fmi2Instantiate!(governor_fmu; type = fmi2TypeCoSimulation)
        if (
            fmi2SetupExperiment(plant, 0.0, 4.0; tolerance = 1.0e-10)
            == fmi2StatusOK
            && fmi2SetupExperiment(governor, 0.0, 4.0; tolerance = 1.0e-10)
            == fmi2StatusOK
            && fmi2EnterInitializationMode(plant) == fmi2StatusOK
            && fmi2EnterInitializationMode(governor) == fmi2StatusOK
            && fmi2SetReal(governor, "K", 4.0) == fmi2StatusOK
            && fmi2SetReal(plant, "MECH_CONTROL", 0.0) == fmi2StatusOK
            && fmi2SetReal(governor, "SPEED", 0.0) == fmi2StatusOK
            && fmi2ExitInitializationMode(plant) == fmi2StatusOK
            && fmi2ExitInitializationMode(governor) == fmi2StatusOK
        )
            nothing
        else
            error("FMI.jl initialization did not return fmi2StatusOK")
        end

        sample_index::Int = 0
        while sample_index <= step_count
            row_index::Int = sample_index + 1
            current_time::Float64 = sample_index * step_size
            controller_output::Float64 = read_real(governor, "MECH_CONTROL")
            controller_input::Float64 = read_real(governor, "SPEED")
            plant_angle::Float64 = read_real(plant, "ANGLE")
            plant_input::Float64 = read_real(plant, "MECH_CONTROL")
            plant_power::Float64 = read_real(plant, "PELEC")
            plant_speed::Float64 = read_real(plant, "SPEED")
            plant_reactance::Float64 = read_real(plant, "X_EFFECTIVE")
            trace[row_index, 1] = current_time
            trace[row_index, 2] = controller_output
            trace[row_index, 3] = controller_input
            trace[row_index, 4] = plant_angle
            trace[row_index, 5] = plant_input
            trace[row_index, 6] = plant_power
            trace[row_index, 7] = plant_speed
            trace[row_index, 8] = plant_reactance

            if sample_index < step_count
                # Both inputs are committed before either slave advances, so
                # execution order cannot turn the Jacobi exchange into Gauss-Seidel.
                if (
                    fmi2SetReal(plant, "MECH_CONTROL", controller_output)
                    == fmi2StatusOK
                    && fmi2SetReal(governor, "SPEED", plant_speed)
                    == fmi2StatusOK
                    && fmi2DoStep(
                        plant,
                        step_size;
                        currentCommunicationPoint = current_time,
                    ) == fmi2StatusOK
                    && fmi2DoStep(
                        governor,
                        step_size;
                        currentCommunicationPoint = current_time,
                    ) == fmi2StatusOK
                )
                    nothing
                else
                    error("FMI.jl communication step did not return fmi2StatusOK")
                end
            else
                nothing
            end
            sample_index += 1
        end
    finally
        if plant === nothing
            nothing
        else
            fmi2Terminate(plant; soft = true)
            fmi2FreeInstance!(plant)
        end
        if governor === nothing
            nothing
        else
            fmi2Terminate(governor; soft = true)
            fmi2FreeInstance!(governor)
        end
        unloadFMU(plant_fmu)
        unloadFMU(governor_fmu)
    end
    if all(isfinite, trace)
        write_trace(output_path, trace)
        return nothing
    else
        error("FMI.jl produced a non-finite trajectory")
    end
end


"""Validate explicit arguments and execute the benchmark."""
function main(arguments::Vector{String})::Int
    if length(arguments) == 5
        plant_path::String = arguments[1]
        plant_sha256::String = lowercase(arguments[2])
        governor_path::String = arguments[3]
        governor_sha256::String = lowercase(arguments[4])
        output_path::String = arguments[5]
        verify_input(plant_path, plant_sha256)
        verify_input(governor_path, governor_sha256)
        execute_composition(plant_path, governor_path, output_path)
        verify_input(plant_path, plant_sha256)
        verify_input(governor_path, governor_sha256)
        println("Julia $(VERSION)")
        println("FMI.jl $(pkgversion(FMI))")
        println("PASS FMI.jl rows=2001 signals=7")
        return 0
    else
        error(
            "Expected plant path/hash, governor path/hash and output CSV path",
        )
    end
end


exit(main(ARGS))
