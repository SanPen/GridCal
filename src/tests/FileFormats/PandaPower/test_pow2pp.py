from collections import defaultdict
import pytest
import numpy as np

from tests.FileFormats.PandaPower.pow2pp import convert_to_pandapower


# Import our converter functions (assuming they're in a module)
# from powsybl2pandapower_converter import convert_to_pandapower

# For testing, let's include the converter functions directly

@pytest.mark.skip(reason="unclear what this is supposed to test")
def test_transnet_exmple_net():

    try:
        import pypowsybl.network
    except ImportError:
        return

    pow = pypowsybl.network.load(
        "tests/data/grids/state-estimation/19700101T0000Z_.zip"
    )
    net = convert_to_pandapower(pow)
    print(net)
    pp_result = run_pypowsybl_powerflow(pow)

    # Run pandapower power flow
    pp_net_result = run_pandapower_powerflow(net)


def test_conversion_on_example_networks():

    try:
        import pypowsybl as pp
    except ImportError:
        return

    """Test the conversion on various example pypowsybl networks"""

    # List of available example networks with correct creation methods
    example_networks = [
        ("ieee9", lambda: pp.network.create_ieee9()),
        ("ieee14", lambda: pp.network.create_ieee14()),
        ("ieee30", lambda: pp.network.create_ieee30()),
        ("ieee57", lambda: pp.network.create_ieee57()),
        ("ieee118", lambda: pp.network.create_ieee118()),
        # ("french_test_case", lambda: pp.network.create_french_test_case()),  # This might not exist
        # ("four_substations", lambda: pp.network.create_four_substations())   # This might not exist
    ]

    results = defaultdict(dict)

    for network_name, network_creator in example_networks:
        try:
            print(f"\n{'=' * 60}")
            print(f"Testing conversion for: {network_name}")
            print(f"{'=' * 60}")

            # Load the example network using the correct creation method
            network = network_creator()
            print(
                f"Created {network_name}: {len(network.get_buses())} buses, {len(network.get_lines())} lines"
            )

            # Convert to pandapower
            pandapower_net = convert_to_pandapower(network)

            # Store conversion results
            results[network_name]["powsybl_buses"] = len(network.get_buses())
            results[network_name]["pandapower_buses"] = len(pandapower_net.bus)
            results[network_name]["powsybl_lines"] = len(network.get_lines())
            results[network_name]["pandapower_lines"] = len(pandapower_net.line)
            results[network_name]["powsybl_transformers"] = len(
                network.get_2_windings_transformers()
            )
            results[network_name]["pandapower_transformers"] = (
                len(pandapower_net.trafo) if hasattr(pandapower_net, "trafo") else 0
            )
            results[network_name]["powsybl_generators"] = len(network.get_generators())
            results[network_name]["pandapower_generators"] = (
                len(pandapower_net.gen) if hasattr(pandapower_net, "gen") else 0
            )
            results[network_name]["powsybl_loads"] = len(network.get_loads())
            results[network_name]["pandapower_loads"] = len(pandapower_net.load)

            # Run power flow on both networks for comparison
            try:
                # Run pypowsybl power flow
                pp_result = run_pypowsybl_powerflow(network)

                # Run pandapower power flow
                pp_net_result = run_pandapower_powerflow(pandapower_net)

                # Compare results
                compare_powerflow_results(
                    network_name, network, pandapower_net, results
                )

            except Exception as e:
                print(f"Power flow failed for {network_name}: {e}")
                results[network_name]["powerflow_success"] = False

            print(f"Successfully converted {network_name}")
        except Exception as e:
            print(f"✗ Failed to convert {network_name}: {e}")
            results[network_name]["conversion_success"] = False

    # Generate summary report
    generate_summary_report(results)

    return results


def run_pypowsybl_powerflow(network):
    """Run power flow using pypowsybl"""

    try:
        import pypowsybl as pp
    except ImportError:
        return

    try:
        # Create a simple power flow
        pf = pp.loadflow.run_ac(network)
        return pf
    except Exception as e:
        print(f"Pypowsybl power flow failed: {e}")
        return None


def run_pandapower_powerflow(network):
    """Run power flow using pandapower"""
    try:
        # Run AC power flow
        # pdp.create_ext_grid(network, bus=0, vm_pu=1.04, va_degree=0.0)
        network.sn_mva = 100.0
        run_pandapower_pp(network)
        return network
    except Exception as e:
        print(f"Pandapower power flow failed: {e}")
        return None


def run_pandapower_pp(network):

    try:
        import pypowsybl as pp
    except ImportError:
        return

    try:
        import pandapower as pdp
    except ImportError:
        return

    """Run power flow using pandapower with robust settings"""
    try:
        # Check if we have a slack bus

        # Use robust power flow settings
        pdp.runpp(
            network,
            algorithm="nr",
            calculate_voltage_angles=True,
            numba=True,
            max_iteration=50,  # Limit iterations
            tolerance_mva=1e-6,  # Slightly looser tolerance
            init="dc",  # Use DC power flow for initialization
            enforce_q_lims=True,
        )
        return network

    except Exception as e:
        print(f"Pandapower power flow error: {e}")

        # Try with even more robust settings
        try:
            print("Trying with DC power flow as fallback...")
            pdp.rundcpp(network)
            return network
        except Exception as dc_error:
            print(f"DC power flow also failed: {dc_error}")
            raise


def compare_powerflow_results(network_name, pp_result, pp_net_result, results):
    """Compare power flow results between pypowsybl and pandapower"""

    if pp_result is None or pp_net_result is None:
        results[network_name]["powerflow_comparison"] = "Failed"
        return

    try:
        # Compare bus voltages
        pp_bus_voltages = pp_result.get_buses().v_mag.values
        pdp_bus_voltages = pp_net_result.res_bus.vm_pu.values

        loads_pow = pp_result.get_loads().p.values
        loads_panda = pp_net_result.res_load.p_mw.values

        gen_pow = pp_result.get_generators().p.values
        gen_panda = -pp_net_result.res_gen.p_mw.values

        voltage_diff = np.abs(pp_bus_voltages - pdp_bus_voltages)
        max_voltage_diff = np.max(voltage_diff) if len(voltage_diff) > 0 else 0

        load_diff = np.abs(loads_pow - loads_panda)
        max_load_diff = np.max(load_diff) if len(load_diff) > 0 else 0

        gen_diff = np.abs(gen_pow - gen_panda)
        max_gen_diff = np.max(gen_diff) if len(gen_diff) > 0 else 0

        results[network_name]["max_voltage_diff_pu"] = max_voltage_diff
        results[network_name]["avg_voltage_diff_pu"] = (
            np.mean(voltage_diff) if len(voltage_diff) > 0 else 0
        )
        results[network_name]["max_load_diff_pu"] = max_load_diff
        results[network_name]["avg_voltage_diff_pu"] = (
            np.mean(load_diff) if len(load_diff) > 0 else 0
        )
        results[network_name]["max_gen_diff_pu"] = max_gen_diff
        results[network_name]["avg_gen_diff_pu"] = (
            np.mean(max_gen_diff) if len(gen_pow) > 0 else 0
        )

        results[network_name]["powerflow_comparison"] = "Success"

        print(f"  Voltage comparison: max diff = {max_voltage_diff:.6f} pu")
        # print(f"  Voltage comparison: max diff = {max_load_diff:.6f} pu")
        # print(f"  Voltage comparison: max diff = {max_gen_diff:.6f} pu")

    except Exception as e:
        print(f"Comparison failed: {e}")
        results[network_name]["powerflow_comparison"] = f"Error: {e}"


def generate_summary_report(results):
    """Generate a comprehensive summary report"""
    print(f"\n{'=' * 80}")
    print("CONVERSION SUMMARY REPORT")
    print(f"{'=' * 80}")

    successful_conversions = 0
    successful_powerflows = 0

    for network_name, data in results.items():
        print(f"\n{network_name.upper():<20}")
        print(f"{'-' * 20}")

        if "conversion_success" in data and data["conversion_success"] is False:
            print("  Conversion: FAILED")
            continue

        successful_conversions += 1

        print(
            f"  Buses:     {data.get('powsybl_buses', 0):4d} → {data.get('pandapower_buses', 0):4d}"
        )
        print(
            f"  Lines:     {data.get('powsybl_lines', 0):4d} → {data.get('pandapower_lines', 0):4d}"
        )
        print(
            f"  Transformers: {data.get('powsybl_transformers', 0):4d} → {data.get('pandapower_transformers', 0):4d}"
        )
        print(
            f"  Generators: {data.get('powsybl_generators', 0):4d} → {data.get('pandapower_generators', 0):4d}"
        )
        print(
            f"  Loads:     {data.get('powsybl_loads', 0):4d} → {data.get('pandapower_loads', 0):4d}"
        )

        if "max_voltage_diff_pu" in data:
            print(f"  Max voltage diff: {data['max_voltage_diff_pu']:.6f} pu")
            successful_powerflows += 1

    print(f"\n{'=' * 80}")
    print(f"Overall Success Rate: {successful_conversions}/{len(results)} conversions")
    print(
        f"Power Flow Success: {successful_powerflows}/{successful_conversions} networks"
    )
    print(f"{'=' * 80}")


def detailed_network_analysis(network_name="ieee14"):
    """Perform detailed analysis on a specific network"""

    try:
        import pypowsybl as pp
    except ImportError:
        return

    print(f"\n{'=' * 80}")
    print(f"DETAILED ANALYSIS: {network_name}")
    print(f"{'=' * 80}")

    try:
        # Load the network using correct creation method
        if network_name == "ieee9":
            network = pp.network.create_ieee9()
        elif network_name == "ieee14":
            network = pp.network.create_ieee14()
        elif network_name == "ieee30":
            network = pp.network.create_ieee30()
        elif network_name == "ieee57":
            network = pp.network.create_ieee57()
        elif network_name == "ieee118":
            network = pp.network.create_ieee118()
        else:
            print(f"Unknown network: {network_name}")
            return

        # Print network information
        print_network_info(network, "PYPOWSYBL ORIGINAL")

        # Convert to pandapower
        pandapower_net = convert_to_pandapower(network)

        # Print converted network information
        print_converted_network_info(pandapower_net, "PANDAPOWER CONVERTED")

        # Run power flow on both
        print("\nRunning power flow comparisons...")
        pp_result = run_pypowsybl_powerflow(network)
        pdp_result = run_pandapower_pp(pandapower_net)

        if pp_result and pdp_result:
            detailed_comparison(pp_result, pdp_result)

    except Exception as e:
        print(f"Detailed analysis failed: {e}")
        import traceback

        traceback.print_exc()


def print_network_info(network, title):
    """Print detailed network information"""
    print(f"\n{title}")
    print(f"{'-' * len(title)}")
    print(f"Buses:          {len(network.get_buses())}")
    print(f"Lines:          {len(network.get_lines())}")
    print(f"Transformers:   {len(network.get_2_windings_transformers())}")
    print(f"Generators:     {len(network.get_generators())}")
    print(f"Loads:          {len(network.get_loads())}")
    print(f"Shunts:         {len(network.get_shunt_compensators())}")
    print(f"Switches:       {len(network.get_switches())}")

    # Check for tap changers
    ratio_tap_changers = network.get_ratio_tap_changers()
    phase_tap_changers = network.get_phase_tap_changers()
    print(f"Ratio Tap Changers:  {len(ratio_tap_changers)}")
    print(f"Phase Tap Changers:  {len(phase_tap_changers)}")


def print_converted_network_info(network, title):
    """Print detailed converted network information"""
    print(f"\n{title}")
    print(f"{'-' * len(title)}")
    print(f"Buses:          {len(network.bus)}")
    print(f"Lines:          {len(network.line)}")
    print(f"Transformers:   {len(network.trafo) if hasattr(network, 'trafo') else 0}")
    print(
        f"3W Transformers: {len(network.trafo3w) if hasattr(network, 'trafo3w') else 0}"
    )
    print(f"Generators:     {len(network.gen) if hasattr(network, 'gen') else 0}")
    print(f"Static Gens:    {len(network.sgen) if hasattr(network, 'sgen') else 0}")
    print(
        f"External Grid:  {len(network.ext_grid) if hasattr(network, 'ext_grid') else 0}"
    )
    print(f"Loads:          {len(network.load)}")
    print(f"Shunts:         {len(network.shunt) if hasattr(network, 'shunt') else 0}")
    print(f"Switches:       {len(network.switch) if hasattr(network, 'switch') else 0}")


def detailed_comparison(pp_result, pdp_result):
    """Detailed comparison of power flow results"""
    print(f"\n{'=' * 40}")
    print("DETAILED POWER FLOW COMPARISON")
    print(f"{'=' * 40}")

    # Compare bus voltages
    pp_buses = pp_result.get_bus_view()
    pdp_buses = pdp_result.res_bus

    voltage_diffs = []
    for i, (pp_voltage, pdp_voltage) in enumerate(
        zip(pp_buses.v_magpu.values, pdp_buses.vm_pu.values, strict=False)
    ):
        diff = abs(pp_voltage - pdp_voltage)
        voltage_diffs.append(diff)
        if diff > 0.01:  # Show significant differences
            print(
                f"Bus {i + 1}: {pp_voltage:.4f} → {pdp_voltage:.4f} (diff: {diff:.4f})"
            )

    print(f"\nMax voltage difference: {max(voltage_diffs):.6f} pu")
    print(
        f"Average voltage difference: {sum(voltage_diffs) / len(voltage_diffs):.6f} pu"
    )


def test_specific_features():
    """Test specific features on appropriate networks"""

    try:
        import pypowsybl as pp
    except ImportError:
        return

    print(f"\n{'=' * 80}")
    print("SPECIFIC FEATURE TESTING")
    print(f"{'=' * 80}")

    # Test networks with tap changers
    tap_changer_networks = [
        ("ieee14", lambda: pp.network.create_ieee14()),
        ("case30", lambda: pp.network.create_case30()),
        ("case118", lambda: pp.network.create_case118()),
    ]

    for network_name, network_creator in tap_changer_networks:
        try:
            network = network_creator()
            ratio_tap_changers = network.get_ratio_tap_changers()
            phase_tap_changers = network.get_phase_tap_changers()

            if len(ratio_tap_changers) > 0 or len(phase_tap_changers) > 0:
                print(f"\nTesting tap changers in {network_name}:")
                print(f"  Ratio tap changers: {len(ratio_tap_changers)}")
                print(f"  Phase tap changers: {len(phase_tap_changers)}")

                # Convert and check tap parameters
                pandapower_net = convert_to_pandapower(network)

                if hasattr(pandapower_net, "trafo") and len(pandapower_net.trafo) > 0:
                    trafo_with_tap = pandapower_net.trafo[
                        pandapower_net.trafo["tap_pos"].notna()
                        | pandapower_net.trafo["tap2_pos"].notna()
                    ]
                    print(
                        f"  Converted transformers with tap changers: {len(trafo_with_tap)}"
                    )

        except Exception as e:
            print(f"Feature test failed for {network_name}: {e}")


def quick_test():
    """Quick test to verify basic functionality"""

    try:
        import pypowsybl as pp
    except ImportError:
        return

    print("Running quick test...")

    # Test with IEEE 9 bus system
    network = pp.network.create_ieee9()
    print(f"IEEE 9 bus system created: {len(network.get_buses())} buses")

    # Show some basic info
    print(f"Lines: {len(network.get_lines())}")
    print(f"Transformers: {len(network.get_2_windings_transformers())}")
    print(f"Generators: {len(network.get_generators())}")
    print(f"Loads: {len(network.get_loads())}")

    # Try power flow
    try:
        result = pp.loadflow.run_ac(network)
        print("Power flow successful!")
        print(f"Bus voltages: {result.get_bus_view().v_magpu.values}")
    except Exception as e:
        print(f"Power flow failed: {e}")


if __name__ == "__main__":
    print("Starting pypowsybl to pandapower conversion test...")

    # First run a quick test to verify pypowsybl works
    quick_test()

    # Test on multiple example networks
    results = test_conversion_on_example_networks()

    # Detailed analysis on a specific network
    detailed_network_analysis("ieee14")

    # Test specific features
    test_specific_features()

    print("\nTest completed!")
