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

Ns = 50

b = [ 0.0 ]*Ns
c = [ 0.0 ]*Ns
d = [ 0.0 ]*Ns

b[1] = tworoot/6.0
b[2] = 1.0/16.0
c[2] = 1.3659315
d[2] = pi*b[2]/4.0
nsign = 1
for n in range(3, Ns):
   nsign = pow(-1, (n + 1)/2 % 2)
#   nsign = pow(-1, (n - 1)/4 % 2)
   if n < 22:
      print >>sys.stderr, n, nsign
   b[n] = nsign*b[n - 2]/(n*(n + 2.0))
   c[n] = c[n - 2] + 1.0/n + 1.0/(n + 2)
   d[n] = pi*b[n]/4.0

def J(p, q):
   global Ns
   a = sqrt(p*p + q*q)
   th = atan2(q, p)
   ah = 0.5*a
   lna = log(a)
   ap = [ 0.0 ]*32
   cthp = [ 0.0 ]*32
   sthp = [ 0.0 ]*32
   for n in range(32):
      ap[n] = pow(a, n)
      cthp[n] = cos(n*th)
      sthp[n] = sin(n*th)
      if n > 23:
         ap[n] = 0.0
         cthp[n] = 0.0
         sthp[n] = 0.0

   P = pi/8.0 \
     - b[1]*ap[1]*cthp[1] \
     + b[2]*( (c[2] - lna)*ap[2]*cthp[2] + th*ap[2]*sthp[2] ) \
     + b[3]*ap[3]*cthp[3] \
     - d[4]*ap[4]*cthp[4] \
     - b[5]*ap[5]*cthp[5] \
     + b[6]*( (c[6] - lna)*ap[6]*cthp[6] + th*ap[6]*sthp[6] ) \
     + b[7]*ap[7]*cthp[7] \
     - d[8]*ap[8]*cthp[8] \
     - b[9]*ap[9]*cthp[9] \
     + b[10]*( (c[10] - lna)*ap[10]*cthp[10] + th*ap[10]*sthp[10] ) \
     + b[11]*ap[11]*cthp[11] \
     - d[12]*ap[12]*cthp[12] \
     - b[13]*ap[13]*cthp[13] \
     + b[14]*( (c[14] - lna)*ap[14]*cthp[14] + th*ap[14]*sthp[14] ) \
     + b[15]*ap[15]*cthp[15] \
     - d[16]*ap[16]*cthp[16] \
     - b[17]*ap[17]*cthp[17] \
     + b[18]*( (c[18] - lna)*ap[18]*cthp[18] + th*ap[18]*sthp[18] ) \
     + b[19]*ap[19]*cthp[19] \
     - d[20]*ap[20]*cthp[20] \
     - b[21]*ap[21]*cthp[21] \
     + b[22]*( (c[22] - lna)*ap[22]*cthp[22] + th*ap[22]*sthp[22] ) \
     + b[23]*ap[23]*cthp[23] \
     - d[24]*ap[24]*cthp[24] \
     - b[25]*ap[25]*cthp[25]
   Q = (1.0/2.0)*(0.6159315 - lna) \
     + b[1]*ap[1]*cthp[1] \
     - d[2]*ap[2]*cthp[2] \
     + b[3]*ap[3]*cthp[3] \
     - b[4]*( (c[4] - lna)*ap[4]*cthp[4] + th*ap[4]*sthp[4] ) \
     + b[5]*ap[5]*cthp[5] \
     - d[6]*ap[6]*cthp[6] \
     + b[7]*ap[7]*cthp[7] \
     - b[8]*( (c[8] - lna)*ap[8]*cthp[8] + th*ap[8]*sthp[8] ) \
     + b[9]*ap[9]*cthp[9] \
     - d[10]*ap[10]*cthp[10] \
     + b[11]*ap[11]*cthp[11] \
     - b[12]*( (c[12] - lna)*ap[12]*cthp[12] + th*ap[12]*sthp[12] ) \
     + b[13]*ap[13]*cthp[13] \
     - d[14]*ap[14]*cthp[14] \
     + b[15]*ap[15]*cthp[15] \
     - b[16]*( (c[16] - lna)*ap[16]*cthp[16] + th*ap[16]*sthp[16] ) \
     + b[17]*ap[17]*cthp[17] \
     - d[18]*ap[18]*cthp[18] \
     + b[19]*ap[19]*cthp[19] \
     - b[20]*( (c[20] - lna)*ap[20]*cthp[20] + th*ap[20]*sthp[20] ) \
     + b[21]*ap[21]*cthp[21] \
     - d[22]*ap[22]*cthp[22] \
     + b[23]*ap[23]*cthp[23]
   return P + 1.0j*Q

def Jr_big(r):
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
      print 's', nth, r, Jre
      print 's', nth + Nth, r, Jim
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
