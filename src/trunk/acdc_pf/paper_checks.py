import os
import io
# import matlab.engine
import threading
import sys
import numpy as np
import faulthandler
# import results_handler
# from matlab_parser import parse_matlab_case

# Add the path to GridCalEngine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'GridCal', 'src')))
import GridCalEngine as gce
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.enumerations import SolverType, ConverterControlType


def run_5bus_MatACDC(num_iterations=10):
    # Path to the output text file
    output_file = 'MatACDCoutput5bus.txt'

    # Empty the content of the file by opening it in write mode
    with open(output_file, 'w'):
        pass  # Just open and close to clear any content

    # Start the MATLAB engine
    eng = matlab.engine.start_matlab()

    # Get the current working directory
    current_directory = os.getcwd()

    # Generate the paths for all subfolders using genpath
    subfolders = eng.genpath(current_directory)
    # exclude the subfolder 'Paper ACDC'
    subfolders = subfolders.split(os.pathsep)
    subfolders = [x for x in subfolders if 'Paper ACDC' not in x]
    subfolders = os.pathsep.join(subfolders)

    # Add the paths to MATLAB's search path
    eng.addpath(subfolders, nargout=0)

    # Verify the path
    current_path = eng.path()
    # Optionally print the current path to verify
    # print(current_path)

    verbose = 1

    # Run your MATLAB function (modify as per your specific use case)
    eng.pfDriverCode5bus(verbose, nargout=0)
    times = eng.pfTimingCode5bus(num_iterations, nargout=1)

    # Stop the MATLAB engine
    eng.quit()

    return times


def run_39bus_MatACDC(num_iterations=10):
    # Path to the output text file
    output_file = 'MatACDCoutput39bus.txt'

    # Empty the content of the file by opening it in write mode
    with open(output_file, 'w'):
        pass  # Just open and close to clear any content

    # Start the MATLAB engine
    eng = matlab.engine.start_matlab()

    # Get the current working directory
    current_directory = os.getcwd()

    # Generate the paths for all subfolders using genpath
    subfolders = eng.genpath(current_directory)
    # exclude the subfolder 'Paper ACDC'
    subfolders = subfolders.split(os.pathsep)
    subfolders = [x for x in subfolders if 'Paper ACDC' not in x]
    subfolders = os.pathsep.join(subfolders)

    # Add the paths to MATLAB's search path
    eng.addpath(subfolders, nargout=0)

    # Verify the path
    current_path = eng.path()
    # Optionally print the current path to verify
    # print(current_path)

    verbose = 1

    # Run your MATLAB function (modify as per your specific use case)
    eng.pfDriverCode39bus(verbose, nargout=0)
    times = eng.pfTimingCode39bus(num_iterations, nargout=1)

    # Stop the MATLAB engine
    eng.quit()

    return times


def run_96bus_MatACDC(num_iterations=10):
    # Path to the output text file
    output_file = 'MatACDCoutput96bus.txt'

    # Empty the content of the file by opening it in write mode
    with open(output_file, 'w'):
        pass  # Just open and close to clear any content

    # Start the MATLAB engine
    eng = matlab.engine.start_matlab()

    # Get the current working directory
    current_directory = os.getcwd()

    # Generate the paths for all subfolders using genpath
    subfolders = eng.genpath(current_directory)
    # exclude the subfolder 'Paper ACDC'
    subfolders = subfolders.split(os.pathsep)
    subfolders = [x for x in subfolders if 'Paper ACDC' not in x]
    subfolders = os.pathsep.join(subfolders)

    # Add the paths to MATLAB's search path
    eng.addpath(subfolders, nargout=0)

    # Verify the path
    current_path = eng.path()
    # Optionally print the current path to verify
    # print(current_path)
    verbose = 1

    # Run your MATLAB function (modify as per your specific use case)
    eng.pfDriverCode96bus(verbose, nargout=0)
    times = eng.pfTimingCode96bus(num_iterations, nargout=1)

    # Stop the MATLAB engine
    eng.quit()

    return times


def run_3120bus_MatACDC(num_iterations=10):
    # Path to the output text file
    output_file = 'MatACDCoutput3120bus.txt'

    # Empty the content of the file by opening it in write mode
    with open(output_file, 'w'):
        pass  # Just open and close to clear any content

    # Start the MATLAB engine
    eng = matlab.engine.start_matlab()

    # Get the current working directory
    current_directory = os.getcwd()

    # Generate the paths for all subfolders using genpath
    subfolders = eng.genpath(current_directory)
    # exclude the subfolder 'Paper ACDC'
    subfolders = subfolders.split(os.pathsep)
    subfolders = [x for x in subfolders if 'Paper ACDC' not in x]
    subfolders = os.pathsep.join(subfolders)

    # Add the paths to MATLAB's search path
    eng.addpath(subfolders, nargout=0)

    # Verify the path
    current_path = eng.path()
    # Optionally print the current path to verify
    # print(current_path)
    verbose = 1

    # Run your MATLAB function (modify as per your specific use case)
    eng.pfDriverCode3120bus(verbose, nargout=0)
    times = eng.pfTimingCode3120bus(num_iterations, nargout=1)

    # Stop the MATLAB engine
    eng.quit()

    return times


faulthandler.enable()  # start @ the beginning


def run_time_5bus(verbose=1):
    """
    Check that a transformer can regulate the voltage at a bus and write results to a text file.
    Captures the console output if verbose is True.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(current_dir, 'grids', 'case5_3_he.gridcal')

    grid = gce.open_file(fname)

    options = PowerFlowOptions(SolverType.NR,
                               verbose=verbose,
                               control_q=False,
                               retry_with_other_methods=False,
                               control_taps_phase=False,
                               control_taps_modules=False,
                               max_iter=80,
                               tolerance=1e-8, )

    # Capture the original stdout
    original_stdout = sys.stdout
    if verbose:
        # Redirect stdout to a string (capture the output)
        captured_output = io.StringIO()
        sys.stdout = captured_output

    # Run the power flow
    results = gce.power_flow(grid, options)

    # Reset stdout to original
    sys.stdout = original_stdout

    if verbose:
        # Return captured output and results
        return results.elapsed, results.get_bus_df(), captured_output.getvalue()
    else:
        return results.elapsed


def run_time_39bus(verbose=1):
    """
    Run the power flow for a 39-bus system and output results to a text file.
    Captures the console output if verbose is True.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(current_dir, 'grids', 'case39_10_he.gridcal')

    grid = gce.open_file(fname)

    # Set control parameters for VSC devices
    # grid.vsc_devices[0].control1 = ConverterControlType.Pac
    # grid.vsc_devices[1].control1 = ConverterControlType.Pac
    # grid.vsc_devices[2].control1 = ConverterControlType.Pac
    # grid.vsc_devices[3].control1 = ConverterControlType.Vm_dc
    # grid.vsc_devices[3].control1_val = 1.0
    # grid.vsc_devices[4].control1 = ConverterControlType.Pac
    # grid.vsc_devices[5].control1 = ConverterControlType.Pac
    # grid.vsc_devices[6].control1 = ConverterControlType.Pac
    # grid.vsc_devices[7].control1 = ConverterControlType.Pac
    # grid.vsc_devices[8].control1 = ConverterControlType.Pac
    # grid.vsc_devices[9].control1 = ConverterControlType.Pac

    # for j in range(len(grid.vsc_devices)):
    #     print(grid.vsc_devices[j].name)
    #     print("control1:", grid.vsc_devices[j].control1)
    #     print("control1val:", grid.vsc_devices[j].control1_val)
    #     print("control2:", grid.vsc_devices[j].control2)
    #     print("control2val:", grid.vsc_devices[j].control2_val)

    options = PowerFlowOptions(SolverType.NR,
                               verbose=verbose,
                               control_q=True,
                               retry_with_other_methods=False,
                               control_taps_phase=True,
                               control_taps_modules=True,
                               max_iter=80,
                               tolerance=1e-8, )

    # Capture the original stdout
    original_stdout = sys.stdout
    if verbose:
        # Redirect stdout to capture output
        captured_output = io.StringIO()
        sys.stdout = captured_output

    # Run the power flow
    results = gce.power_flow(grid, options)

    # Reset stdout to original
    sys.stdout = original_stdout

    if verbose:
        # Return captured output and results
        return results.elapsed, results.get_bus_df(), captured_output.getvalue()
    else:
        return results.elapsed


def run_time_96bus(verbose=1):
    """
    Run the power flow for a 96-bus system and output results to a text file.
    Captures the console output if verbose is True.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(current_dir, 'grids', 'case96.gridcal')

    grid = gce.open_file(fname)
    grid.vsc_devices[5].control1 = ConverterControlType.Pdc
    grid.vsc_devices[5].control1_val = 50.0

    options = PowerFlowOptions(SolverType.NR,
                               verbose=verbose,
                               control_q=False,
                               retry_with_other_methods=False,
                               control_taps_phase=True,
                               control_taps_modules=True,
                               max_iter=80,
                               tolerance=1e-8, )

    # Capture the original stdout
    original_stdout = sys.stdout
    if verbose:
        # Redirect stdout to capture output
        captured_output = io.StringIO()
        sys.stdout = captured_output

    # Run the power flow
    results = gce.power_flow(grid, options)

    # Reset stdout to original
    sys.stdout = original_stdout

    if verbose:
        # Return captured output and results
        return results.elapsed, results.get_bus_df(), captured_output.getvalue()
    else:
        return results.elapsed


def run_time_3kbus(verbose=1):
    """
    Run the power flow for a 3120-bus system and output results to a text file.
    Captures the console output if verbose is True.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.join(current_dir, 'grids', 'case3120_5_he.gridcal')

    grid = gce.open_file(fname)

    options = PowerFlowOptions(SolverType.NR,
                               verbose=verbose,
                               control_q=False,
                               retry_with_other_methods=False,
                               control_taps_phase=True,
                               control_taps_modules=True,
                               max_iter=80,
                               tolerance=1e-8, )

    # Capture the original stdout
    original_stdout = sys.stdout
    if verbose:
        # Redirect stdout to capture output
        captured_output = io.StringIO()
        sys.stdout = captured_output

    # Run the power flow
    results = gce.power_flow(grid, options)

    # Reset stdout to original
    sys.stdout = original_stdout

    if verbose:
        # Return captured output and results
        return results.elapsed, results.get_bus_df(), captured_output.getvalue()
    else:
        return results.elapsed


def run_timing_test(func, iterations=100):
    """
    Run the power flow function in a loop and collect timing data
    """
    if iterations == 1:
        iterations = 2

    times = np.zeros(iterations)

    # Set verbose to 0 for timing to avoid unnecessary printing
    options = PowerFlowOptions(SolverType.NR,
                               verbose=0,  # disable verbose output during timing
                               control_q=False,
                               retry_with_other_methods=False,
                               control_taps_phase=False,
                               control_taps_modules=False,
                               max_iter=80,
                               tolerance=1e-8, )

    for i in range(iterations):
        elapsed = func(verbose=0)
        times[i] = elapsed

    # Print the timing statistics
    # print(f"Mean time: {np.mean(times)} seconds")
    # print(f"Times list: {times}")
    return times[1:]  # avoid the first


def scale_grid_loads(grid, scaling_factor):
    """
    Multiply all real and reactive loads in the grid by the given scaling factor.
    Also scales VSC power controls (Pdc and Qac) and generator active power by the same factor.
    This does not overwrite the grid file—only modifies the object in memory.

    Parameters:
        grid (MultiCircuit): GridCal grid object.
        scaling_factor (float): Scaling multiplier (e.g., 2.0, 3.0).
    """
    # Scale loads
    loads_dict = grid.get_elements_dict_by_type(element_type=gce.DeviceType.LoadDevice)
    for key, load in loads_dict.items():
        if load.bus is None:
            continue  # just to be safe
        load.P *= scaling_factor
        load.Q *= scaling_factor

    # Scale generators
    generators_dict = grid.get_elements_dict_by_type(element_type=gce.DeviceType.GeneratorDevice)
    for key, generator in generators_dict.items():
        if generator.bus is None:
            continue  # just to be safe
        generator.P *= scaling_factor

    # Scale VSC power controls
    for vsc in grid.vsc_devices:
        # Scale control1 if it's power-related
        if vsc.control1 in [ConverterControlType.Pdc, ConverterControlType.Qac]:
            vsc.control1_val *= scaling_factor

        # Scale control2 if it's power-related
        if vsc.control2 in [ConverterControlType.Pdc, ConverterControlType.Qac]:
            vsc.control2_val *= scaling_factor


def test_convergence_with_scaled_loads(grid_file, scaling_factors=None, verbose=1):
    """
    Test convergence behavior with different load scaling factors.

    Parameters:
        grid_file (str): Path to the grid file
        scaling_factors (list): List of scaling factors to test (default: [1.0, 2.0, 3.0, 4.0])
        verbose (int): Verbosity level

    Returns:
        dict: Results dictionary with scaling factors as keys and results as values
    """
    if scaling_factors is None:
        scaling_factors = [1.0, 2.0, 3.0, 4.0, 5.0]

    results_dict = {}

    options = PowerFlowOptions(SolverType.NR,
                               verbose=verbose,
                               control_q=False,
                               retry_with_other_methods=False,
                               control_taps_phase=False,
                               control_taps_modules=False,
                               max_iter=80,
                               tolerance=1e-8)

    for factor in scaling_factors:
        print(f"Testing with load scaling factor: {factor}")

        # Load fresh grid for each test
        grid = gce.open_file(grid_file)

        # Scale the loads
        scale_grid_loads(grid, factor)

        # Capture output if verbose
        original_stdout = sys.stdout
        if verbose:
            captured_output = io.StringIO()
            sys.stdout = captured_output

        # Run power flow
        try:
            results = gce.power_flow(grid, options)

            # Reset stdout
            sys.stdout = original_stdout

            # Store results
            results_dict[factor] = {
                'elapsed_time': results.elapsed,
                'converged': results.converged,
                'iterations': results.iterations,
                'error': results.error,
                'bus_df': results.get_bus_df(),
                'captured_output': captured_output.getvalue() if verbose else None
            }

            print(f"  - Elapsed time: {results.elapsed:.6f} seconds")
            print(f"  - Converged: {results.converged}")
            print(f"  - Iterations: {results.iterations}")
            print(f"  - Final error: {results.error:.2e}")

        except Exception as e:
            sys.stdout = original_stdout
            print(f"  - ERROR: {str(e)}")
            results_dict[factor] = {
                'elapsed_time': None,
                'converged': False,
                'iterations': None,
                'error': float('inf'),
                'bus_df': None,
                'captured_output': None,
                'exception': str(e)
            }

    return results_dict


def run_convergence_test(grid_file, system_name="SYSTEM", start_factor=1.0, step_size=1.0, max_factor=100.0,
                         ac_matlab_file=None, dc_matlab_file=None):
    """
    Run convergence test for any grid system, scaling loads until first failure.
    Also generates scaled MATLAB files for each scaling factor tested.

    Parameters:
        grid_file (str): Path to the GridCal .gridcal file
        system_name (str): Name of the system for display purposes
        start_factor (float): Starting scaling factor
        step_size (float): Increment for each test
        max_factor (float): Maximum scaling factor to prevent infinite loop
        ac_matlab_file (str, optional): Path to AC MATLAB .m file to scale and output
        dc_matlab_file (str, optional): Path to DC MATLAB .m file to scale and output
    """
    print("=" * 60)
    print(f"CONVERGENCE TEST: {system_name} WITH SCALED LOADS")
    print("=" * 60)
    print(f"Testing from {start_factor}x to failure (max {max_factor}x, step {step_size})")

    # Show what will be scaled - analyze the grid first
    test_grid = gce.open_file(grid_file)
    loads_dict = test_grid.get_elements_dict_by_type(element_type=gce.DeviceType.LoadDevice)
    generators_dict = test_grid.get_elements_dict_by_type(element_type=gce.DeviceType.GeneratorDevice)
    print(f"Will scale {len(loads_dict)} load devices")
    print(f"Will scale {len(generators_dict)} generator devices (Pmin/Pmax set to ±9999)")

    vsc_power_controls = []
    for i, vsc in enumerate(test_grid.vsc_devices):
        if vsc.control1 in [ConverterControlType.Pdc, ConverterControlType.Qac]:
            vsc_power_controls.append(f"VSC{i}({vsc.name}): control1={vsc.control1.name}={vsc.control1_val}")
        if vsc.control2 in [ConverterControlType.Pdc, ConverterControlType.Qac]:
            vsc_power_controls.append(f"VSC{i}({vsc.name}): control2={vsc.control2.name}={vsc.control2_val}")

    if vsc_power_controls:
        print(f"Will scale {len(vsc_power_controls)} VSC power controls:")
        for control in vsc_power_controls:
            print(f"  - {control}")
    else:
        print("No VSC power controls to scale")

    print()

    # Parse MATLAB files once if provided
    ac_parser = None
    dc_parser = None
    if ac_matlab_file and os.path.exists(ac_matlab_file):
        print(f"Parsing AC MATLAB file: {ac_matlab_file}")
        ac_parser = parse_matlab_case(ac_matlab_file)
        print(f"AC file parsed - {len(ac_parser.dataframes)} matrices found")

    if dc_matlab_file and os.path.exists(dc_matlab_file):
        print(f"Parsing DC MATLAB file: {dc_matlab_file}")
        dc_parser = parse_matlab_case(dc_matlab_file)
        print(f"DC file parsed - {len(dc_parser.dataframes)} matrices found")

    print()

    results_dict = {}
    current_factor = start_factor

    options = PowerFlowOptions(SolverType.NR,
                               verbose=0,
                               control_q=False,
                               retry_with_other_methods=False,
                               control_taps_phase=False,
                               control_taps_modules=False,
                               max_iter=80,
                               tolerance=1e-8)

    while current_factor <= max_factor:
        # print(f"Testing with load scaling factor: {current_factor:.1f}", end="")

        # Generate scaled MATLAB files BEFORE testing convergence
        # This ensures we have files for every factor tested, not just successful ones
        if ac_parser:
            ac_scaled_parser = parse_matlab_case(ac_matlab_file)  # Fresh copy
            ac_scaled_parser.scale_loads(current_factor)
            ac_scaled_parser.scale_generators(current_factor)
            ac_scaled_parser.scale_dc_converters(current_factor)

            # Generate output filename
            base_name = os.path.splitext(os.path.basename(ac_matlab_file))[0]
            factor_str = f"x{current_factor:.1f}".replace('.', '_')
            output_name = f"{base_name}_{factor_str}.m"
            output_path = os.path.join(os.path.dirname(ac_matlab_file), output_name)

            ac_scaled_parser.write_matlab_file(output_path)
            print(f"Generated AC file: {output_name} (factor {current_factor:.1f}x)")

        if dc_parser:
            dc_scaled_parser = parse_matlab_case(dc_matlab_file)  # Fresh copy
            dc_scaled_parser.scale_loads(current_factor)
            dc_scaled_parser.scale_generators(current_factor)
            dc_scaled_parser.scale_dc_converters(current_factor)

            # Generate output filename
            base_name = os.path.splitext(os.path.basename(dc_matlab_file))[0]
            factor_str = f"x{current_factor:.1f}".replace('.', '_')
            output_name = f"{base_name}_{factor_str}.m"
            output_path = os.path.join(os.path.dirname(dc_matlab_file), output_name)

            dc_scaled_parser.write_matlab_file(output_path)
            print(f"Generated DC file: {output_name} (factor {current_factor:.1f}x)")

        # Load fresh grid for each test
        grid = gce.open_file(grid_file)

        # Scale the loads
        scale_grid_loads(grid, current_factor)

        # Run power flow
        try:
            results = gce.power_flow(grid, options)

            # Store results
            results_dict[current_factor] = {
                'elapsed_time': results.elapsed,
                'converged': results.converged,
                'iterations': results.iterations,
                'error': results.error,
                'bus_df': results.get_bus_df(),
            }

            if results.converged:
                # print(f" ✓ - Time: {results.elapsed:.6f}s, Iterations: {results.iterations}, Error: {results.error:.2e}")
                current_factor += step_size
            else:
                # print(f" ✗ - FAILED TO CONVERGE (Iterations: {results.iterations}, Error: {results.error:.2e})")
                break

        except Exception as e:
            print(f" ✗ - ERROR: {str(e)}")
            results_dict[current_factor] = {
                'elapsed_time': None,
                'converged': False,
                'iterations': None,
                'error': float('inf'),
                'bus_df': None,
                'exception': str(e)
            }
            break

    # Print summary
    max_successful_factor = max([f for f, r in results_dict.items() if r['converged']], default=0)

    print()
    print("=" * 60)
    print("CONVERGENCE LIMIT ANALYSIS")
    print("=" * 60)
    print(f"Maximum successful load scaling: {max_successful_factor:.2f}x")
    print(f"First failure at scaling: {current_factor:.2f}x")
    print(f"Total successful tests: {sum(1 for r in results_dict.values() if r['converged'])}")

    results = results_dict

    print("\n" + "=" * 60)
    print("CONVERGENCE TEST SUMMARY")
    print("=" * 60)
    print(f"{'Load Factor':<12} {'Time (s)':<12} {'Converged':<10} {'Iterations':<12} {'Final Error':<15}")
    print("-" * 75)

    scaling_factors = sorted(results.keys())

    for factor in scaling_factors:
        result = results[factor]
        if 'exception' in result:
            print(f"{factor:<12.2f} {'ERROR':<12} {'False':<10} {'N/A':<12} {'N/A':<15}")
        else:
            elapsed = result['elapsed_time']
            converged = result['converged']
            iterations = result['iterations']
            error = result['error']

            elapsed_str = f"{elapsed:.6f}" if elapsed is not None else "N/A"
            iter_str = str(iterations) if iterations is not None else "N/A"
            error_str = f"{error:.2e}" if error != float('inf') else "INF"

            print(f"{factor:<12.1f} {elapsed_str:<12} {str(converged):<10} {iter_str:<12} {error_str:<15}")

    return results


def generate_driver_file(ac_file_path, dc_file_path, output_txt_file, driver_file_path):
    """
    Generate a MATLAB driver file for running factored ACDC power flow cases.

    Parameters:
        ac_file_path (str): Path to the AC MATLAB file (without .m extension)
        dc_file_path (str): Path to the DC MATLAB file (without .m extension)
        output_txt_file (str): Name of the output text file for diary
        driver_file_path (str): Path where to save the driver .m file
    """
    # Extract just the case names without path and extension
    ac_case_name = os.path.splitext(os.path.basename(ac_file_path))[0]
    dc_case_name = os.path.splitext(os.path.basename(dc_file_path))[0]
    driver_function_name = os.path.splitext(os.path.basename(driver_file_path))[0]

    driver_content = f"""function {driver_function_name}(verbose)
    diary('{output_txt_file}');
    acdcOpt = macdcoption;
    acdcOpt(13) = verbose;
    runacdcpf('{ac_case_name}', '{dc_case_name}', acdcOpt);
    diary off;
    fclose('all');
end
"""

    with open(driver_file_path, 'w') as f:
        f.write(driver_content)

    print(f"Generated driver file: {os.path.basename(driver_file_path)}")


def run_factored_matlab_case(ac_file_path, dc_file_path, system_name="FACTORED SYSTEM", num_iterations=1):
    """
    Run MatACDC power flow for factored MATLAB case files.

    Parameters:
        ac_file_path (str): Path to the factored AC MATLAB .m file
        dc_file_path (str): Path to the factored DC MATLAB .m file
        system_name (str): Name for display and output file naming
        num_iterations (int): Number of iterations for timing

    Returns:
        numpy.array: Array of execution times
    """
    # Extract factor from filename for naming
    ac_basename = os.path.splitext(os.path.basename(ac_file_path))[0]
    if '_x' in ac_basename:
        factor_part = ac_basename.split('_x')[-1]
        # Keep underscores for all file names - no periods in MATLAB function names
        factor_str = factor_part  # Don't replace underscores with periods
    else:
        factor_str = "1_0"

    # Create output files with factor in name (using underscores consistently)
    output_file = f'MatACDCoutput_{system_name.lower().replace("-", "").replace(" ", "")}_{factor_str}x.txt'
    driver_file = f'pfDriverCode_{system_name.lower().replace("-", "").replace(" ", "")}_{factor_str}x.m'

    # Convert factor_str back to readable format for display
    display_factor = factor_str.replace('_', '.')
    print(f"Running MatACDC for {system_name} (factor {display_factor}x)...")

    # Empty the content of the output file
    with open(output_file, 'w'):
        pass

    # Generate the driver file for this factored case
    generate_driver_file(
        ac_file_path=ac_file_path,
        dc_file_path=dc_file_path,
        output_txt_file=output_file,
        driver_file_path=driver_file
    )

    # Start the MATLAB engine
    eng = matlab.engine.start_matlab()

    # Get the current working directory
    current_directory = os.getcwd()

    # Generate the paths for all subfolders using genpath
    subfolders = eng.genpath(current_directory)
    # Exclude the subfolder 'Paper ACDC'
    subfolders = subfolders.split(os.pathsep)
    subfolders = [x for x in subfolders if 'Paper ACDC' not in x]
    subfolders = os.pathsep.join(subfolders)

    # Add the paths to MATLAB's search path
    eng.addpath(subfolders, nargout=0)

    verbose = 1

    try:
        # Extract function name from driver file
        driver_function_name = os.path.splitext(os.path.basename(driver_file))[0]

        # Run the generated driver function
        eng.eval(f"{driver_function_name}({verbose})", nargout=0)

        print(f"✓ MatACDC execution completed for {system_name} (factor {display_factor}x)")
        print(f"  Output saved to: {output_file}")

        # For timing, we could run multiple iterations, but for now return a single time
        # This would need to be implemented similar to the timing functions if needed
        times = np.array([1.0])  # Placeholder - actual timing would need more complex implementation

    except Exception as e:
        print(f"✗ Error running MatACDC for {system_name} (factor {display_factor}x): {str(e)}")
        times = np.array([np.inf])

    finally:
        # Stop the MATLAB engine
        eng.quit()

    return times


def run_all_factored_matlab_cases(grid_directory="grids", system_name="SYSTEM", pattern_prefix="case"):
    """
    Find and run all factored MATLAB case files in the specified directory.

    Parameters:
        grid_directory (str): Directory containing the MATLAB files
        system_name (str): System name for output file naming
        pattern_prefix (str): Prefix pattern to match case files (e.g., "case3120_5_he")

    Returns:
        dict: Dictionary with factor as key and execution results as values
    """
    results = {}

    # Find all factored AC files
    ac_files = []
    dc_files = []

    for filename in os.listdir(grid_directory):
        if filename.startswith(pattern_prefix) and filename.endswith('.m') and '_x' in filename:
            if '_ac_x' in filename:
                ac_files.append(os.path.join(grid_directory, filename))
            elif '_dc_x' in filename:
                dc_files.append(os.path.join(grid_directory, filename))

    # Sort files by factor
    def extract_factor(filepath):
        basename = os.path.splitext(os.path.basename(filepath))[0]
        if '_x' in basename:
            factor_part = basename.split('_x')[-1]
            return float(factor_part.replace('_', '.'))  # Only for sorting - convert back to float
        return 1.0

    ac_files.sort(key=extract_factor)
    dc_files.sort(key=extract_factor)

    print(f"Found {len(ac_files)} AC factored files and {len(dc_files)} DC factored files")

    # Match AC and DC files by factor
    for ac_file in ac_files:
        ac_factor = extract_factor(ac_file)

        # Find corresponding DC file
        dc_file = None
        for dc_candidate in dc_files:
            if abs(extract_factor(dc_candidate) - ac_factor) < 0.001:  # floating point comparison
                dc_file = dc_candidate
                break

        if dc_file:
            print(f"\n{'=' * 50}")
            print(f"Running factored case: {ac_factor}x")
            print(f"AC file: {os.path.basename(ac_file)}")
            print(f"DC file: {os.path.basename(dc_file)}")
            print(f"{'=' * 50}")

            try:
                times = run_factored_matlab_case(
                    ac_file_path=ac_file,
                    dc_file_path=dc_file,
                    system_name=system_name,
                    num_iterations=1
                )
                results[ac_factor] = {
                    'times': times,
                    'ac_file': ac_file,
                    'dc_file': dc_file,
                    'success': True
                }
            except Exception as e:
                print(f"✗ Error processing factor {ac_factor}x: {str(e)}")
                results[ac_factor] = {
                    'times': np.array([np.inf]),
                    'ac_file': ac_file,
                    'dc_file': dc_file,
                    'success': False,
                    'error': str(e)
                }
        else:
            print(f"⚠ No matching DC file found for AC factor {ac_factor}x")

    return results


if __name__ == '__main__':
    # Run convergence test for 5-bus system with scaled loads
    # print("Running convergence test for 5-bus system with scaled loads...")
    # current_dir = os.path.dirname(os.path.abspath(__file__))
    # fname_5bus = os.path.join(current_dir, 'grids', 'case5_3_he.gridcal')
    # ac_matlab_5 = os.path.join(current_dir, 'grids', 'case5_3_he_ac.m')
    # dc_matlab_5 = os.path.join(current_dir, 'grids', 'case5_3_he_dc.m')
    # convergence_results_5bus = run_convergence_test(
    #     grid_file=fname_5bus,
    #     system_name="5-BUS SYSTEM",
    #     start_factor=1.0,
    #     step_size=0.1,  # More granular testing
    #     max_factor=2.0,  # Reasonable upper limit
    #     ac_matlab_file=ac_matlab_5,
    #     dc_matlab_file=dc_matlab_5
    # )

    # print("\nConvergence test for 5-bus system completed.\n")
    # print("Results:")
    # for factor, result in convergence_results_5bus.items():
    #     print(f"Factor {factor:.1f}x: Converged={result['converged']}, "
    #           f"Time={result['elapsed_time']:.6f}s, "
    #           f"Iterations={result['iterations']}, "
    #           f"Error={result['error']:.2e}")

    # print("Running convergence test for 39-bus system with scaled loads...")
    # fname_39bus = os.path.join(current_dir, 'grids', 'case39_10_he.gridcal')
    # convergence_results_39bus = run_convergence_test(
    #     grid_file=fname_39bus,
    #     system_name="39-BUS SYSTEM",
    #     start_factor=1.0,
    #     step_size=0.5,  # More granular testing
    #     max_factor=50.0  # Reasonable upper limit
    # )

    # print("\nConvergence test for 39-bus system completed.\n")
    # print("Results:")
    # for factor, result in convergence_results_39bus.items():
    #     print(f"Factor {factor:.1f}x: Converged={result['converged']}, "
    #           f"Time={result['elapsed_time']:.6f}s, "
    #           f"Iterations={result['iterations']}, "
    #           f"Error={result['error']:.2e}")

    # print("Running convergence test for 96-bus system with scaled loads...")
    # fname_96bus = os.path.join(current_dir, 'grids', 'case96.gridcal')
    # convergence_results_96bus = run_convergence_test(
    #     grid_file=fname_96bus,
    #     system_name="96-BUS SYSTEM",
    #     start_factor=1.0,
    #     step_size=0.5,  # More granular testing
    #     max_factor=50.0  # Reasonable upper limit
    # )
    # print("\nConvergence test for 96-bus system completed.\n")
    # print("Results:")
    # for factor, result in convergence_results_96bus.items():
    #     print(f"Factor {factor:.1f}x: Converged={result['converged']}, "
    #           f"Time={result['elapsed_time']:.6f}s, "
    #           f"Iterations={result['iterations']}, "
    #           f"Error={result['error']:.2e}")

    # current_dir = os.path.dirname(os.path.abspath(__file__))
    # print("Running convergence test for 3120-bus system with scaled loads...")
    # fname_3120bus = os.path.join(current_dir, 'grids', 'case3120_5_he.gridcal')
    # ac_matlab_3120 = os.path.join(current_dir, 'grids', 'case3120_5_he_ac.m')
    # dc_matlab_3120 = os.path.join(current_dir, 'grids', 'case3120_5_he_dc.m')
    #
    # convergence_results_3120bus = run_convergence_test(
    #     grid_file=fname_3120bus,
    #     system_name="3120-BUS SYSTEM",
    #     start_factor=1.0,
    #     step_size=0.1,  # More granular testing
    #     max_factor=50.0,  # Reasonable upper limit
    #     ac_matlab_file=ac_matlab_3120,
    #     dc_matlab_file=dc_matlab_3120
    # )
    # print("\nConvergence test for 3120-bus system completed.\n")
    # print("Results:")
    # for factor, result in convergence_results_3120bus.items():
    #     print(f"Factor {factor:.1f}x: Converged={result['converged']}, "
    #           f"Time={result['elapsed_time']:.6f}s, "
    #           f"Iterations={result['iterations']}, "
    #           f"Error={result['error']:.2e}")

    # print("MatACDC - Running 5-bus grid case...")
    # matACDC_convergenceTime5bus = run_5bus_MatACDC(num_iterations=1)
    # print("MatACDC - Running 39-bus grid case...")
    # matACDC_convergenceTime39bus = run_39bus_MatACDC(num_iterations=1)
    # print("MatACDC - Running 96-bus grid case...")
    # matACDC_convergenceTime96bus = run_96bus_MatACDC(num_iterations=1)
    # print("MatACDC - Running 3120-bus grid case...")
    # matACDC_convergenceTime3120bus = run_3120bus_MatACDC(num_iterations=1)

    # Run all factored MATLAB cases that were generated
    # print("\n" + "="*60)
    # print("RUNNING ALL FACTORED MATLAB CASES")
    # print("="*60)
    # factored_results = run_all_factored_matlab_cases(
    #     grid_directory="grids",
    #     system_name="3120-BUS SYSTEM",
    #     pattern_prefix="case3120_5_he"
    # )
    #
    # print(f"\n{'='*60}")
    # print("FACTORED MATLAB RESULTS SUMMARY")
    # print("="*60)
    # for factor, result in sorted(factored_results.items()):
    #     status = "✓" if result['success'] else "✗"
    #     print(f"Factor {factor:4.1f}x: {status} - AC: {os.path.basename(result['ac_file'])}")
    #     if not result['success']:
    #         print(f"            Error: {result.get('error', 'Unknown error')}")
    # print("="*60)
    #
    # print("GridCal - Running 5-bus grid case...")
    # gridcal_elapsed_5bus, gridcal_bus_df_5bus, gridcal_iostring_5bus = run_time_5bus()
    # print("GridCal - Running 39-bus grid case...")
    # gridcal_elapsed_39bus, gridcal_bus_df_39bus, gridcal_iostring_39bus = run_time_39bus()
    # print("GridCal - Running 96-bus grid case...")
    # gridcal_elapsed_96bus, gridcal_bus_df_96bus, gridcal_iostring_96bus = run_time_96bus()
    # print("GridCal - Running 3120-bus grid case...")
    # gridcal_elapsed_3120bus, gridcal_bus_df_3120bus, gridcal_iostring_3120bus = run_time_3kbus()
    #
    # Timing the executions for 10 iterations
    print("GridCal - Timing for 5-bus grid case...")
    gridcal_time5bus = run_timing_test(run_time_5bus, iterations=10)
    print("GridCal - Timing for 39-bus grid case...")
    gridcal_time39bus = run_timing_test(run_time_39bus, iterations=10)
    # print("GridCal - Timing for 96-bus grid case...")
    # gridcal_time96bus = run_timing_test(run_time_96bus, iterations=10)
    print("GridCal - Timing for 3120-bus grid case...")
    gridcal_time3120bus = run_timing_test(run_time_3kbus, iterations=10)
    #
    #
    # print("MatACDC - Convergence times for 5 bus system: ", matACDC_convergenceTime5bus)
    # print("MatACDC - Convergence times for 39 bus system: ", matACDC_convergenceTime39bus)
    # print("MatACDC - Convergence times for 96 bus system: ", matACDC_convergenceTime96bus)
    # print("MatACDC - Convergence times for 3120 bus system: ", matACDC_convergenceTime3120bus)
    #
    print("Time list for 5-bus grid case", gridcal_time5bus, np.mean(gridcal_time5bus))
    print("Time list for 39-bus grid case", gridcal_time39bus, np.mean(gridcal_time39bus))
    # print("Time list for 96-bus grid case", gridcal_time96bus, np.mean(gridcal_time96bus))
    print("Time list for 3120-bus grid case", gridcal_time3120bus, np.mean(gridcal_time3120bus))
    #
    # # Initializing the ResultsHandler with all necessary data
    # results_handler = results_handler.ResultsHandler(
    #     mat5bus_times=matACDC_convergenceTime5bus,
    #     mat39bus_times=matACDC_convergenceTime39bus,
    #     mat96bus_times=matACDC_convergenceTime96bus,
    #     mat3120bus_times=matACDC_convergenceTime3120bus,
    #     grid5bus_df=gridcal_bus_df_5bus,
    #     grid39bus_df=gridcal_bus_df_39bus,
    #     grid96bus_df=gridcal_bus_df_96bus,
    #     grid3120bus_df=gridcal_bus_df_3120bus,
    #     grid5bus_times=gridcal_time5bus,
    #     grid39bus_times=gridcal_time39bus,
    #     grid96bus_times=gridcal_time96bus,
    #     grid3120bus_times=gridcal_time3120bus,
    #     mat5bus_output='MatACDCoutput5bus.txt',
    #     mat39bus_output='MatACDCoutput39bus.txt',
    #     mat96bus_output='MatACDCoutput96bus.txt',
    #     mat3120bus_output='MatACDCoutput3120bus.txt',
    #     grid5bus_output=gridcal_iostring_5bus,
    #     grid39bus_output=gridcal_iostring_39bus,
    #     grid96bus_output=gridcal_iostring_96bus,
    #     grid3120bus_output=gridcal_iostring_3120bus
    # )
    #
    #
    # results_handler.draw_combined_error_evolution()
    # results_handler.save_separate_error_plots()
    # results_handler.plot_voltage_histograms(num_buckets=7)
    # results_handler.plot_voltage_histograms_separate(num_buckets=7)
    # results_handler.draw_time_comparison_table()
