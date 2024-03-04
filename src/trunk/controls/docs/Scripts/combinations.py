from itertools import combinations

# Variables
variables = ['D', 'V', 'P', 'Q', 'I']

combinations_of_2 = list(combinations(variables, 2))
combinations_of_3 = list(combinations(variables, 3))
combinations_of_4 = list(combinations(variables, 4))

print(combinations_of_2)
print(combinations_of_3)
print(combinations_of_4)