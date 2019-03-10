#!/usr/local/bin/python

import sys, math
from math import sin, cos, atan2, sqrt, exp, log, pi
import cmath

Euler = 0.577215664901532860606512
gamma = exp(Euler)
ln2g = log(2.0/gamma)
lng = Euler
tpi = 2.0*pi
tworoot = sqrt(2.0)

Nmax = 150
F = [ 0.0 ]*Nmax

# Generate table of factorials, non-recursively
F[0] = 1.0
for n in range(1, Nmax):
   F[n] = n*F[n - 1]

Ns = 6

def sum_inv(m):
   sum = 1.0 - 1.0/(2.0*m)
   for mx in range(2, m + 1):
      sum += 1.0/float(mx)
   return sum

def prod_xsq(m):
   prod = float(m)
   for mx in range(1, m/2):
      prod *= float((2*mx + 1)*(2*mx + 1))
   return prod

def prod_xsqL(m):
   prod = m
   for mx in range(1, m/2):
      prod *= (2*mx + 1)*(2*mx + 1)
   return float(prod)

if 0: # order of multiplication for prod_xsq(21) matters in the last bit
   print >>sys.stderr, prod_xsq(21)
   print >>sys.stderr, ((((((((float(21)*float(3*3))*float(5*5))*float(7*7))*float(9*9))*float(11*11))*float(13*13))*float(15*15))*float(17*17))*float(19*19)
   print >>sys.stderr, float(3*3)*float(5*5)*float(7*7)*float(9*9)*float(11*11)*float(13*13)*float(15*15)*float(17*17)*float(19*19)*float(21)
   x = 21.0
   x *= float(3*3)
   x *= float(5*5)
   x *= float(7*7)
   x *= float(9*9)
   x *= float(11*11)
   x *= float(13*13)
   x *= float(15*15)
   x *= float(17*17)
   x *= float(19*19)
   print >>sys.stderr, prod_xsq(21) - float(3*3)*float(5*5)*float(7*7)*float(9*9)*float(11*11)*float(13*13)*float(15*15)*float(17*17)*float(19*19)*float(21)
   print >>sys.stderr, prod_xsq(21) - ((((((((float(21)*float(3*3))*float(5*5))*float(7*7))*float(9*9))*float(11*11))*float(13*13))*float(15*15))*float(17*17))*float(19*19)
   print >>sys.stderr, prod_xsq(21) - ((((((((float(3*3)*float(21))*float(5*5))*float(7*7))*float(9*9))*float(11*11))*float(13*13))*float(15*15))*float(17*17))*float(19*19)
   print >>sys.stderr, prod_xsq(21) - x
   sys.exit(0)

if 0:
   print >>sys.stderr, sum_inv(2) - (1.0 + 1.0/2.0 - 1.0/4.0)
   print >>sys.stderr, sum_inv(3) - (1.0 + 1.0/2.0 + 1.0/3.0 - 1.0/6.0)
   print >>sys.stderr, sum_inv(4) - (1.0 + 1.0/2.0 + 1.0/3.0 + 1.0/4.0 - 1.0/8.0)
   print >>sys.stderr, sum_inv(5) - (1.0 + 1.0/2.0 + 1.0/3.0 + 1.0/4.0 + 1.0/5.0  - 1.0/10.0)
   print >>sys.stderr, sum_inv(6) - (1.0 + 1.0/2.0 + 1.0/3.0 + 1.0/4.0 + 1.0/5.0 + 1.0/6.0 - 1.0/12.0)
   print >>sys.stderr, sum_inv(7) - (1.0 + 1.0/2.0 + 1.0/3.0 + 1.0/4.0 + 1.0/5.0 + 1.0/6.0 + 1.0/7.0 - 1.0/14.0)
   print >>sys.stderr, sum_inv(8) - (1.0 + 1.0/2.0 + 1.0/3.0 + 1.0/4.0 + 1.0/5.0 + 1.0/6.0 + 1.0/7.0 + 1.0/8.0 - 1.0/16.0)
   print >>sys.stderr, sum_inv(9) - (1.0 + 1.0/2.0 + 1.0/3.0 + 1.0/4.0 + 1.0/5.0 + 1.0/6.0 + 1.0/7.0 + 1.0/8.0 + 1.0/9.0 - 1.0/18.0)
   print >>sys.stderr, sum_inv(10) - (1.0 + 1.0/2.0 + 1.0/3.0 + 1.0/4.0 + 1.0/5.0 + 1.0/6.0 + 1.0/7.0 + 1.0/8.0 + 1.0/9.0 + 1.0/10.0 - 1.0/20.0)
   print >>sys.stderr, prod_xsq(1) - (1)
   print >>sys.stderr, prod_xsq(3) - (3)
   print >>sys.stderr, prod_xsq(5) - (3*3*5)
   print >>sys.stderr, prod_xsq(7) - (3*3*5*5*7)
   print >>sys.stderr, prod_xsq(9) - (3*3*5*5*7*7*9)
   print >>sys.stderr, prod_xsq(11) - (3*3*5*5*7*7*9*9*11)
   print >>sys.stderr, prod_xsq(13) - (3*3*5*5*7*7*9*9*11*11*13)
   print >>sys.stderr, prod_xsq(15) - (3*3*5*5*7*7*9*9*11*11*13*13*15)
   print >>sys.stderr, prod_xsq(17) - (3*3*5*5*7*7*9*9*11*11*13*13*15*15*17)
   print >>sys.stderr, prod_xsq(19) - (3*3*5*5*7*7*9*9*11*11*13*13*15*15*17*17*19)
   print >>sys.stderr, prod_xsq(21) - float(21)*float(3*3)*float(5*5)*float(7*7)*float(9*9)*float(11*11)*float(13*13)*float(15*15)*float(17*17)*float(19*19)
   print >>sys.stderr, prod_xsqL(21) - float(3*3*5*5*7*7*9*9*11*11*13*13*15*15*17*17*19*19*21)
   print >>sys.stderr, prod_xsq(23) - (3*3*5*5*7*7*9*9*11*11*13*13*15*15*17*17*19*19*21*21*23)
   print >>sys.stderr, prod_xsq(25) - (3*3*5*5*7*7*9*9*11*11*13*13*15*15*17*17*19*19*21*21*23*23*25)
   print >>sys.stderr, prod_xsq(27) - float(3*3*5*5*7*7)*float(9*9*11*11)*float(13*13*15*15)*float(17*17*19*19)*float(21*21*23*23)*float(25*25*27)
   sys.exit(0)

SI = [ 0.0 ]*101
PX = [ 0.0 ]*102
for n in range(1, 101):
   SI[n] = sum_inv(n)
for n in range(1, 102, 2):
   PX[n] = prod_xsqL(n)

#print PX
#sys.exit(0)

def J(p, q):
   global F
   global gamma
   global Ns
   r = sqrt(p*p + q*q)
   th = atan2(q, p)
   rh = 0.5*r
   lnr = log(r)
   rp = [ 0.0 ]*32
   rhp = [ 0.0 ]*32
   cthp = [ 0.0 ]*32
   sthp = [ 0.0 ]*32
   for n in range(32):
      rp[n] = pow(r, n)
      rhp[n] = pow(rh, n)
      cthp[n] = cos(n*th)
      sthp[n] = sin(n*th)
      if n > 32: # cuts off series a specific r^n term
         rp[n] = 0.0
         rhp[n] = 0.0
         cthp[n] = 0.0
         sthp[n] = 0.0

   s2 = 0.0
   s2p = 0.0
   nf = 1
   nsign = 1
   for ns in range(Ns):
      np = 2 + 4*ns
      s2 += nsign*(1.0/(F[nf]*F[nf + 1]))*rhp[np]*cthp[np]
      s2p += nsign*(1.0/(F[nf]*F[nf + 1]))*rhp[np]*sthp[np]
      nf += 2
      nsign = -nsign

   s4 = 0.0
   s4p = 0.0
   nf = 2
   nsign = 1
   for ns in range(Ns):
      np = 4 + 4*ns
      s4 += nsign*(1.0/(F[nf]*F[nf + 1]))*rhp[np]*cthp[np]
      s4p += nsign*(1.0/(F[nf]*F[nf + 1]))*rhp[np]*sthp[np]
      nf += 2
      nsign = -nsign

   sg1 = 0.0
   nsign = 1
   nden = 3
   for ns in range(Ns):
      np = 1 + 4*ns
      den = PX[nden]
      sg1 += nsign*rp[np]*cthp[np]/den
      nsign = -nsign
      nden += 4

   sg3 = 0.0
   nsign = 1
   nden = 5
   for ns in range(Ns):
      np = 3 + 4*ns
      den = PX[nden]
      sg3 += nsign*rp[np]*cthp[np]/den
      nsign = -nsign
      nden += 4
      
   sg2 = 0.0
   nsign = 1
   nfrac = 2
   nf = 1
   for ns in range(Ns):
      np = 2 + 4*ns
      nfr = 2
      num = SI[nfrac]
      sg2 += nsign*num*(1.0/(F[nf]*F[nf + 1]))*rhp[np]*cthp[np]
      nsign = -nsign
      nfrac += 2
      nf += 2
      
   sg4 = 0.0
   nsign = 1
   nfrac = 3
   nf = 2
   for ns in range(Ns):
      np = 4 + 4*ns
      nfr = 2
      num = SI[nfrac]
      sg4 += nsign*num*(1.0/(F[nf]*F[nf + 1]))*rhp[np]*cthp[np]
      nsign = -nsign
      nfrac += 2
      nf += 2

   P = (pi/8.0)*(1.0 - s4) + 0.5*(log(2.0/gamma) - lnr)*s2 + 0.5*th*s2p \
     - sg1/tworoot + 0.5*sg2 + sg3/tworoot
   Q = 0.25 + 0.5*(log(2.0/gamma) - lnr)*(1.0 - s4) - 0.5*th*s4p \
     + sg1/tworoot - (pi/8.0)*s2 + sg3/tworoot - 0.5*sg4
   return P + 1.0j*Q

debug_terms = False
debug_coefs = False

def Jr(r):
   global F
   global gamma
   global Ns
   global th

   rh = 0.5*r
   s2 = 0.0
   s2p = 0.0
   nf = 1
   nsign = 1
   for ns in range(Ns):
      np = 2 + 4*ns
      s2 += nsign*(1.0/(F[nf]*F[nf + 1]))*pow(rh, np)*cos(np*th)
      s2p += nsign*(1.0/(F[nf]*F[nf + 1]))*pow(rh, np)*sin(np*th)
      if debug_terms:
         print >>sys.stderr, 's2: ', ns, nsign*(1.0/(F[nf]*F[nf + 1]))*pow(rh, np)*cos(np*th), \
           nsign*(1.0/(F[nf]*F[nf + 1]))*pow(rh, np)*sin(np*th)
      nf += 2
      nsign = -nsign
   s2x = rh*rh*cos(2.0*th)/(F[1]*F[2]) - pow(rh, 6.0)*cos(6.0*th)/(F[3]*F[4]) \
      + pow(rh, 10.0)*cos(10.0*th)/(F[5]*F[6]) \
      - pow(rh, 14.0)*cos(14.0*th)/(F[7]*F[8]) + pow(rh, 18.0)*cos(18.0*th)/(F[9]*F[10]) \
      - pow(rh, 22.0)*cos(22.0*th)/(F[11]*F[12]) + pow(rh, 26.0)*cos(26.0*th)/(F[13]*F[14])
   s2px = rh*rh*sin(2.0*th)/(F[1]*F[2]) - pow(rh, 6.0)*sin(6.0*th)/(F[3]*F[4]) \
      + pow(rh, 10.0)*sin(10.0*th)/(F[5]*F[6]) \
      - pow(rh, 14.0)*sin(14.0*th)/(F[7]*F[8]) + pow(rh, 18.0)*sin(18.0*th)/(F[9]*F[10]) \
      - pow(rh, 22.0)*sin(22.0*th)/(F[11]*F[12]) + pow(rh, 26.0)*sin(26.0*th)/(F[13]*F[14])

   s4 = 0.0
   s4p = 0.0
   nf = 2
   nsign = 1
   for ns in range(Ns):
      np = 4 + 4*ns
      s4 += nsign*(1.0/(F[nf]*F[nf + 1]))*pow(rh, np)*cos(np*th)
      s4p += nsign*(1.0/(F[nf]*F[nf + 1]))*pow(rh, np)*sin(np*th)
      if debug_terms:
         print >>sys.stderr, 's4: ', ns, nsign*(1.0/(F[nf]*F[nf + 1]))*pow(rh, np)*cos(np*th), \
          nsign*(1.0/(F[nf]*F[nf + 1]))*pow(rh, np)*sin(np*th)
      nf += 2
      nsign = -nsign
   s4x = pow(rh, 4.0)*cos(4.0*th)/(F[2]*F[3]) - pow(rh, 8.0)*cos(8.0*th)/(F[4]*F[5]) \
      + pow(rh, 12.0)*cos(12.0*th)/(F[6]*F[7]) \
      - pow(rh, 16.0)*cos(16.0*th)/(F[8]*F[9]) + pow(rh, 20.0)*cos(20.0*th)/(F[10]*F[11]) \
      - pow(rh, 24.0)*cos(24.0*th)/(F[12]*F[13]) + pow(rh, 28.0)*cos(28.0*th)/(F[14]*F[15])
   s4px = pow(rh, 4.0)*sin(4.0*th)/(F[2]*F[3]) - pow(rh, 8.0)*sin(8.0*th)/(F[4]*F[5]) \
      + pow(rh, 12.0)*sin(12.0*th)/(F[6]*F[7]) \
      - pow(rh, 16.0)*sin(16.0*th)/(F[8]*F[9]) + pow(rh, 20.0)*sin(20.0*th)/(F[10]*F[11]) \
      - pow(rh, 24.0)*sin(24.0*th)/(F[12]*F[13]) + pow(rh, 28.0)*sin(28.0*th)/(F[14]*F[15])

   sg1 = 0.0
   nsign = 1
   nden = 3
   for ns in range(Ns):
      np = 1 + 4*ns
      den = PX[nden]
      if debug_terms:
         print >>sys.stderr, 'sg1: ', ns, nsign*pow(r, np)*cos(np*th)/den
      sg1 += nsign*pow(r, np)*cos(np*th)/den
      nsign = -nsign
      nden += 4
   sg1x = r*cos(th)/3.0 - pow(r, 5)*cos(5.0*th)/(3*3*5*5*7) \
     + pow(r, 9)*cos(9.0*th)/(3*3*5*5*7*7*9*9*11) \
     - pow(r, 13)*cos(13.0*th)/(3*3*5*5*7*7*9*9*11*11*13*13*15) \
     + pow(r, 17)*cos(17.0*th)/(3*3*5*5*7*7*9*9*11*11*13*13*15*15*17*17*19) \
     - pow(r, 21)*cos(21.0*th)/(3*3*5*5*7*7*9*9*11*11*13*13*15*15*17*17*19*19*21*21*23) \
     + pow(r, 25)*cos(25.0*th)/(3*3*5*5*7*7*9*9*11*11*13*13*15*15*17*17*19*19*21*21*23*23*25*25*27)

   sg3 = 0.0
   nsign = 1
   nden = 5
   for ns in range(Ns):
      np = 3 + 4*ns
      den = PX[nden]
      if debug_terms:
         print >>sys.stderr, 'sg3: ', ns, nsign*pow(r, np)*cos(np*th)/den
      sg3 += nsign*pow(r, np)*cos(np*th)/den
      nsign = -nsign
      nden += 4
   sg3x = pow(r, 3)*cos(3.0*th)/(3*3*5) - pow(r, 7)*cos(7.0*th)/(3*3*5*5*7*7*9) \
     + pow(r, 11)*cos(11.0*th)/(3*3*5*5*7*7*9*9*11*11*13) \
     - pow(r, 15)*cos(15.0*th)/(3*3*5*5*7*7*9*9*11*11*13*13*15*15*17) \
     + pow(r, 19)*cos(19.0*th)/(3*3*5*5*7*7*9*9*11*11*13*13*15*15*17*17*19*19*21) \
     - pow(r, 23)*cos(23.0*th)/(3*3*5*5*7*7*9*9*11*11*13*13*15*15*17*17*19*19*21*21*23*23*25) \
     + pow(r, 27)*cos(27.0*th)/(3*3*5*5*7*7*9*9*11*11*13*13*15*15*17*17*19*19*21*21*23*23*25*25*27*27*29)
      
   sg2 = 0.0
   nsign = 1
   nfrac = 2
   nf = 1
   for ns in range(Ns):
      np = 2 + 4*ns
      nfr = 2
      num = SI[nfrac]
      if debug_terms:
         print >>sys.stderr, 'sg2: ', ns, nsign*num*(1.0/(F[nf]*F[nf + 1]))*pow(rh, np)*cos(np*th)
      sg2 += nsign*num*(1.0/(F[nf]*F[nf + 1]))*pow(rh, np)*cos(np*th)
      nsign = -nsign
      nfrac += 2
      nf += 2
   sg2x = sum_inv(2)*pow(rh, 2)*cos(2.0*th)/(F[1]*F[2]) \
     - sum_inv(4)*pow(rh, 6)*cos(6.0*th)/(F[3]*F[4]) \
     + sum_inv(6)*pow(rh, 10)*cos(10.0*th)/(F[5]*F[6]) \
     - sum_inv(8)*pow(rh, 14)*cos(14.0*th)/(F[7]*F[8]) \
     + sum_inv(10)*pow(rh, 18)*cos(18.0*th)/(F[9]*F[10]) \
     - sum_inv(12)*pow(rh, 22)*cos(22.0*th)/(F[11]*F[12]) \
     + sum_inv(14)*pow(rh, 26)*cos(26.0*th)/(F[13]*F[14])
      
   sg4 = 0.0
   nsign = 1
   nfrac = 3
   nf = 2
   for ns in range(Ns):
      np = 4 + 4*ns
      nfr = 2
      num = SI[nfrac]
      if debug_terms:
         print >>sys.stderr, 'sg4: ', ns, nsign*num*(1.0/(F[nf]*F[nf + 1]))*pow(rh, np)*cos(np*th)
      sg4 += nsign*num*(1.0/(F[nf]*F[nf + 1]))*pow(rh, np)*cos(np*th)
      nsign = -nsign
      nfrac += 2
      nf += 2
   sg4x = sum_inv(3)*pow(rh, 4)*cos(4.0*th)/(F[2]*F[3]) \
     - sum_inv(5)*pow(rh, 8)*cos(8.0*th)/(F[4]*F[5]) \
     + sum_inv(7)*pow(rh, 12)*cos(12.0*th)/(F[6]*F[7]) \
     - sum_inv(9)*pow(rh, 16)*cos(16.0*th)/(F[8]*F[9]) \
     + sum_inv(11)*pow(rh, 20)*cos(20.0*th)/(F[10]*F[11]) \
     - sum_inv(13)*pow(rh, 24)*cos(24.0*th)/(F[12]*F[13]) \
     + sum_inv(15)*pow(rh, 28)*cos(28.0*th)/(F[14]*F[15])

   if debug_coefs:
      print >>sys.stderr, '2: ', r, s2, s2x, s2p, s2px
      print >>sys.stderr, '4: ', r, s4, s4x, s4p, s4px
      print >>sys.stderr, 'g13: ', r, sg1, sg1x, sg3, sg3x
      print >>sys.stderr, 'g24: ', r, sg2, sg2x, sg4, sg4x
      print >>sys.stderr

   P = (pi/8.0)*(1.0 - s4) + 0.5*log(2.0/(gamma*r))*s2 + 0.5*th*s2p \
     - sg1/tworoot + 0.5*sg2 + sg3/tworoot
   Q = 0.25 + 0.5*log(2.0/(gamma*r))*(1.0 - s4) - 0.5*th*s4p \
     + sg1/tworoot - (pi/8.0)*s2 + sg3/tworoot - 0.5*sg4
   return P + 1.0j*Q

def Jr_big(r): # Carson's asymptotic form
   global Ns
   global th
   P = -cos(2.0*th)/(r*r)
   P += (cos(th)/r + cos(3.0*th)/pow(r, 3.0) + 3.0*cos(5.0*th)/pow(r, 5.0) \
     - 45.0*cos(7.0*th)/pow(r, 7.0))/tworoot
   Q = (cos(th)/r - cos(3.0*th)/pow(r, 3.0) + 3.0*cos(5.0*th)/pow(r, 5.0) \
     + 45.0*cos(7.0*th)/pow(r, 7.0))/tworoot
   if (r > 10.0):
      P = cos(th)/(tworoot*r) - cos(2.0*th)/(r*r)
      Q = cos(th)/(tworoot*r)
   return P + 1.0j*Q
   
print >>sys.stderr, 'gamma =', gamma
print >>sys.stderr, 'ln2/g =', ln2g
print >>sys.stderr, 'lng =', lng

Nth = 1
Nr = 101
for nth in range(Nth):
   th = 2.0*pi/3.0
   for nr in range(1, Nr):
      r = 0.1*nr
      p = r*cos(th)
      q = r*sin(th)
      Jv = J(p, q)
      Jre = Jv.real
      Jim = Jv.imag
# the following "print" stuff is output to my peculiar plotting program
      print 's', nth, r, Jre
      print 's', nth + Nth, r, Jim
# printing to stderr goes to the screen instead of my plotting program
      print >>sys.stderr, r, Jre, Jim
      if r > 2.0:
         Jvb = Jr_big(r)
         Jre = Jvb.real
         Jim = Jvb.imag
         print 's', nth + 10, r, Jre
         print 's', nth + Nth + 10, r, Jim
      if r < 2.0:
         P = (pi/8.0) - r*cos(th)/(3.0*tworoot) + \
           (r*r/16.0)*cos(2.0*th)*(0.6728 + log(2.0/r)) + (r*r*th/16.0)*sin(2.0*th)
         Q = -0.0386 + 0.5*log(2.0/r) + r*cos(th)/(3.0*tworoot)
         print 's', nth + 20, r, P
         print 's', nth + Nth + 20, r, Q
 
print 'exec autoxy'
