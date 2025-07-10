from GridCalEngine.api import *
from GridCalEngine.Topology import substation_wizards


print('Creating grid...')

# declare a circuit object
grid = MultiCircuit()

country = Country('Spain')
grid.add_country(country)

# subs_vic = substation_wizards.simple_bar('Vic', grid, 2, 1, 220, 41.956664, 2.282089, country=country)

subs_centelles = substation_wizards.simple_bar('Centelles', grid, 1, 1, 220, 41.797790, 2.219917, country=country)


print()

print('Saving grid...')
save_file(grid, 'Test_substations_types_Alex.gridcal')



