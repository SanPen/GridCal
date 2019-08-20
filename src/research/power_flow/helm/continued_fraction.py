''' Calculate e using its simple continued fraction expansion

    See http://stackoverflow.com/q/36077810/4014959

    Also see
    https://en.wikipedia.org/wiki/Continued_fraction#Regular_patterns_in_continued_fractions

    Written by PM 2Ring 2016.03.18
'''

from __future__ import print_function, division
import sys

def contfrac_to_frac(seq):
    ''' Convert the simple continued fraction in `seq`
        into a fraction, num / den
    '''
    num, den = 1, 0
    for u in reversed(seq):
        num, den = den + num*u, num
    return num, den

def e_cont_frac(n):
    ''' Build `n` terms of the simple continued fraction expansion of e
        `n` must be a positive integer
    '''
    seq = [2 * (i+1) // 3 if i%3 == 2 else 1 for i in range(n)]
    seq[0] += 1
    return seq


def main():

    # Get the the number of terms, less one
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    if n < 0:
        print('Argument must be >= 0')
        exit()

    n += 1
    seq = e_cont_frac(n)
    num, den = contfrac_to_frac(seq)

    print('Terms =', n)
    print('Continued fraction:', seq)
    print('Fraction: {0} / {1}'.format(num, den))
    print('Float {0:0.15f}'.format(num / den))

if __name__ == '__main__':
    main()