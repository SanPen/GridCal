from GridCal.Engine import *

# fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Lynn 5 Bus pv.gridcal'
fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE39.gridcal'

main_circuit = FileOpen(fname).open()

get_time_groups(t_array=main_circuit.time_profile, grouping=TimeGrouping.Monthly)

get_time_groups(t_array=main_circuit.time_profile, grouping=TimeGrouping.Weekly)

get_time_groups(t_array=main_circuit.time_profile, grouping=TimeGrouping.Daily)

get_time_groups(t_array=main_circuit.time_profile, grouping=TimeGrouping.Hourly)
