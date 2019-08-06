def print_power_flow_results(power_flow):
    print('\t|V|:', abs(power_flow.results.voltage))
    print('\t|Sbranch|:', abs(power_flow.results.Sbranch))
    print('\t|loading|:', abs(power_flow.results.loading) * 100)
    print('\terr:', power_flow.results.error)
    print('\tConv:', power_flow.results.converged)
