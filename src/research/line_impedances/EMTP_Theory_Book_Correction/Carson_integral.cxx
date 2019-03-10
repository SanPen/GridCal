#include <cstdlib>
#include <cstdio>
#include <cmath>
#include <cstring>

#include <iostream>
#include <sstream>
#include <string>
#include <complex>

//#include <constants.h>
const char sp = ' ';
const char nl = '\n';
const double tworoot = sqrt(2.0);
const double pi = 4.0*atan(1.0);
const double tpi = 2.0*pi;

using namespace std;

double p = 5.0;
double q = 1.0;
complex<double> ci(0.0, 1.0);
double Euler = 0.577215664901532860606512;
double gamma_e = exp(Euler);

const int Nf = 150;
double F[Nf];
const int Nsi = 101;
double SI[Nsi];
double PX[Nsi + 1];

const int Ne = 50;
double b[Ne];
double c[Ne];
double d[Ne];

const int Ns = 8;

double sum_inv(int m)
{
   double sum = 1.0 - 1.0/(2.0*m);
   for(int mx = 2; mx < m + 1; ++mx) // mx in range(2, m + 1):
   {
      sum += 1.0/double(mx);
   }
   return sum;
}

double prod_xsq(int m)
{
   double prod = double(m);
   for(int mx = 1; mx < m/2; ++mx)  //  mx in range(1, m/2):
   {
      prod *= double((2*mx + 1)*(2*mx + 1));
   }
   return prod;
}
void Factorials()
{
   F[0] = 1.0;
   for(int n = 1; n < Nf; ++n)
   {
      F[n] = n*F[n - 1];
   }
   for(int n = 2; n < Nsi; ++n)
   {
      SI[n] = sum_inv(n);
   }
   for(int n = 1; n < Nsi + 1; n += 2)
   {
      PX[n] = prod_xsq(n);
   }
}

void Coeffs() // EMTP Theory Book coefficients
{
   b[1] = tworoot/6.0;
   b[2] = 1.0/16.0;
   c[2] = 1.3659315;
   d[2] = pi*b[2]/4.0;
   double  nsign = 1.0;
   for(int n = 3; n < Ne; ++n)
   {
      nsign = pow(-1.0, (n + 1)/2 % 2); // corrected form
//      nsign = pow(-1.0, (n - 1)/4 % 2); // published version
      b[n] = nsign*b[n - 2]/(n*(n + 2.0));
      c[n] = c[n - 2] + 1.0/n + 1.0/(n + 2);
      d[n] = pi*b[n]/4.0;
   }
}

complex<double> J(double p, double q) // Carson's series
{
   double r = sqrt(p*p + q*q);
   double th = atan2(q, p);
   double rh = 0.5*r;
   double lnr = log(r);
   double rp[32];
   double rhp[32];
   double cthp[32];
   double sthp[32];
   for(int n = 0; n < 32; ++n)
   {
      rp[n] = pow(r, n);
      rhp[n] = pow(rh, n);
      cthp[n] = cos(n*th);
      sthp[n] = sin(n*th);
   }
   double s2 = 0.0;
   double s2p = 0.0;
   int nf = 1;
   int nsign = 1;
   for(int ns = 0; ns < Ns; ++ns)
   {
      int np = 2 + 4*ns;
      s2 += nsign*(1.0/(F[nf]*F[nf + 1]))*rhp[np]*cthp[np];
      s2p += nsign*(1.0/(F[nf]*F[nf + 1]))*rhp[np]*sthp[np];
      nf += 2;
      nsign = -nsign;
      if (isnan(s2) || isnan(s2p))
      {
         cerr << "2 2p : " << ns << sp << np << nl;
         cerr << rhp[np] << sp << cthp[np] << sp << sthp[np] << sp
         << nsign << sp << nf << sp << F[nf] << sp << F[nf + 1] << sp
           << s2 << sp << s2p << nl;
         exit(0);
      }
   }

   double s4 = 0.0;
   double s4p = 0.0;
   nf = 2;
   nsign = 1;
   for(int ns = 0; ns < Ns; ++ns)
   {
      int np = 4 + 4*ns;
      s4 += nsign*(1.0/(F[nf]*F[nf + 1]))*rhp[np]*cthp[np];
      s4p += nsign*(1.0/(F[nf]*F[nf + 1]))*rhp[np]*sthp[np];
      nf += 2;
      nsign = -nsign;
      if (isnan(s4) || isnan(s4p))
      {
         cerr << "4 4p : " << ns << sp << np << nl;
         exit(0);
      }
   }
   
   double sg1 = 0.0;
   nsign = 1;
   int nden = 3;
   for(int ns = 0; ns < Ns; ++ns)
   {
      int np = 1 + 4*ns;
      double den = PX[nden];
      sg1 += nsign*rp[np]*cthp[np]/den;
      nsign = -nsign;
      nden += 4;
      if (isnan(sg1))
      {
         cerr << "g1 : " << ns << sp << np << nl;
         exit(0);
      }
   }

   double sg3 = 0.0;
   nsign = 1;
   nden = 5;
   for(int ns = 0; ns < Ns; ++ns)
   {
      int np = 3 + 4*ns;
      double den = PX[nden];
      sg3 += nsign*rp[np]*cthp[np]/den;
      nsign = -nsign;
      nden += 4;
      if (isnan(sg3))
      {
         cerr << "g3 : " << ns << sp << np << nl;
         exit(0);
      }
   }

   double sg2 = 0.0;
   nsign = 1;
   int nfrac = 2;
   nf = 1;
   for(int ns = 0; ns < Ns; ++ns)
   {
      int np = 2 + 4*ns;
      int nfr = 2;
      double num = SI[nfrac];
      sg2 += nsign*num*(1.0/(F[nf]*F[nf + 1]))*rhp[np]*cthp[np];
      nsign = -nsign;
      nfrac += 2;
      nf += 2;
      if (isnan(sg2))
      {
         cerr << "g2 : " << ns << sp << np << nl;
         exit(0);
      }
   }
      
   double sg4 = 0.0;
   nsign = 1;
   nfrac = 3;
   nf = 2;
   for(int ns = 0; ns < Ns; ++ns)
   {
      int np = 4 + 4*ns;
      int nfr = 2;
      double num = SI[nfrac];
      sg4 += nsign*num*(1.0/(F[nf]*F[nf + 1]))*rhp[np]*cthp[np];
      nsign = -nsign;
      nfrac += 2;
      nf += 2;
      if (isnan(sg4))
      {
         cerr << "g4 : " << ns << sp << np << nl;
         exit(0);
      }
   }
   double P = (pi/8.0)*(1.0 - s4) + 0.5*(log(2.0/gamma_e) - lnr)*s2 + 0.5*th*s2p
     - sg1/tworoot + 0.5*sg2 + sg3/tworoot;
   double Q = 0.25 + 0.5*(log(2.0/gamma_e) - lnr)*(1.0 - s4) - 0.5*th*s4p
     + sg1/tworoot - (pi/8.0)*s2 + sg3/tworoot - 0.5*sg4;
   return complex<double> (P, Q);
}

complex<double> Je(double p, double q) // EMTP Theory book series
{
   double a = sqrt(p*p + q*q);
   double th = atan2(q, p);
   double ah = 0.5*a;
   double lna = log(a);
   double ap[32];
   double cthp[32];
   double sthp[32];
   for(int n = 0; n < 32; ++n)
   {
      ap[n] = pow(a, n);
      cthp[n] = cos(n*th);
      sthp[n] = sin(n*th);
      if (isnan(ap[n]) || isnan(cthp[n]) || isnan(sthp[n]))
      {
         cerr << "Je : " << n << sp << a << sp << ap[n] << nl;
      }
   }
   double P = pi/8.0 \
     - b[1]*ap[1]*cthp[1]
     + b[2]*( (c[2] - lna)*ap[2]*cthp[2] + th*ap[2]*sthp[2] )
     + b[3]*ap[3]*cthp[3]
     - d[4]*ap[4]*cthp[4]
     - b[5]*ap[5]*cthp[5]
     + b[6]*( (c[6] - lna)*ap[6]*cthp[6] + th*ap[6]*sthp[6] )
     + b[7]*ap[7]*cthp[7]
     - d[8]*ap[8]*cthp[8]
     - b[9]*ap[9]*cthp[9]
     + b[10]*( (c[10] - lna)*ap[10]*cthp[10] + th*ap[10]*sthp[10] )
     + b[11]*ap[11]*cthp[11]
     - d[12]*ap[12]*cthp[12]
     - b[13]*ap[13]*cthp[13]
     + b[14]*( (c[14] - lna)*ap[14]*cthp[14] + th*ap[14]*sthp[14] )
     + b[15]*ap[15]*cthp[15]
     - d[16]*ap[16]*cthp[16]
     - b[17]*ap[17]*cthp[17]
     + b[18]*( (c[18] - lna)*ap[18]*cthp[18] + th*ap[18]*sthp[18] )
     + b[19]*ap[19]*cthp[19]
     - d[20]*ap[20]*cthp[20]
     - b[21]*ap[21]*cthp[21]
     + b[22]*( (c[22] - lna)*ap[22]*cthp[22] + th*ap[22]*sthp[22] )
     + b[23]*ap[23]*cthp[23]
     - d[24]*ap[24]*cthp[24]
     - b[25]*ap[25]*cthp[25];
   double Q = (1.0/2.0)*(0.6159315 - lna)
     + b[1]*ap[1]*cthp[1]
     - d[2]*ap[2]*cthp[2]
     + b[3]*ap[3]*cthp[3]
     - b[4]*( (c[4] - lna)*ap[4]*cthp[4] + th*ap[4]*sthp[4] )
     + b[5]*ap[5]*cthp[5]
     - d[6]*ap[6]*cthp[6]
     + b[7]*ap[7]*cthp[7]
     - b[8]*( (c[8] - lna)*ap[8]*cthp[8] + th*ap[8]*sthp[8] )
     + b[9]*ap[9]*cthp[9]
     - d[10]*ap[10]*cthp[10]
     + b[11]*ap[11]*cthp[11]
     - b[12]*( (c[12] - lna)*ap[12]*cthp[12] + th*ap[12]*sthp[12] )
     + b[13]*ap[13]*cthp[13]
     - d[14]*ap[14]*cthp[14]
     + b[15]*ap[15]*cthp[15]
     - b[16]*( (c[16] - lna)*ap[16]*cthp[16] + th*ap[16]*sthp[16] )
     + b[17]*ap[17]*cthp[17]
     - d[18]*ap[18]*cthp[18]
     + b[19]*ap[19]*cthp[19]
     - b[20]*( (c[20] - lna)*ap[20]*cthp[20] + th*ap[20]*sthp[20] )
     + b[21]*ap[21]*cthp[21]
     - d[22]*ap[22]*cthp[22]
     + b[23]*ap[23]*cthp[23];
   return complex<double> (P, Q);
}

complex<double> CI(double p, double q) // explicit Carson's integral J(p, q)
{
   double r = sqrt(p*p + q*q);
   int N = 10000;
   double mu_max = 10.0;
   double dmu = mu_max/(N);
   complex<double> mu_sum(0.0, 0.0);
   for(int i = 0; i <= N; ++i)
   {
      double ifac;
      if (i == 0 || i == N) ifac = 1.0;
      else ifac = (double)(2*(i % 2) + 2);
      double mu = i*dmu;
      complex<double> arg = (sqrt(mu*mu + ci) - mu)*exp(-p*mu)*cos(q*mu);
      mu_sum += ifac*arg;
// Plot the integrand to make sure both the range and resolution are
// sufficient
      cout << "w 0 " << mu << sp << arg.real() << nl;
      cout << "w 1 " << mu << sp << arg.imag() << nl;
      //cout << "w 2 " << mu << sp << (sqrt(mu*mu + ci) - mu).imag() << nl;
   }
   mu_sum *= dmu/3.0;
//   double P = mu_sum.real();
//   double Q = mu_sum.imag();
   return mu_sum;
}

int main(int argc, char **argv)
{
   if (argc > 1) p = strtod(argv[1], 0);
   if (argc > 2) q = strtod(argv[2], 0);
   Factorials();
   Coeffs();
   double r = sqrt(p*p + q*q);
   complex<double> Jc = CI(p, q);
   cerr << r << sp << Jc.real() << sp << Jc.imag() << endl;
   complex<double> Jv = J(p, q);
   cerr << r << sp << Jv.real() << sp << Jv.imag() << endl;
   complex<double> Jve = Je(p, q);
   cerr << r << sp << Jve.real() << sp << Jve.imag() << endl;
   cout << "n -1\nexec autoxy" << endl;
   return 0;
}
