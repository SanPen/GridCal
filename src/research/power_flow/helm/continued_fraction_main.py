import sys

from research.power_flow.helm.continued_fraction import \
    continue_and_print_fraction

if __name__ == '__main__':
    # Get the the number of terms, less one
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    if n < 0:
        print('Argument must be >= 0')
        exit()

    continue_and_print_fraction(n)
