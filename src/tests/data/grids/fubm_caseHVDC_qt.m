function mpc = fubm_caseHVDC_qt
%%%%%%%%%%%%%%%%%%%%%%%%%% Case HVDC %%%%%%%%%%%%%%%%%%%%%%%%%%%

%% MATPOWER Case Format : Version 2
mpc.version = '2';

%%-----  Power Flow Data  -----%%
%% system MVA base
mpc.baseMVA = 100;

%% bus data
%	bus_i	type	Pd      Qd      Gs      Bs      area    Vm      Va  baseKV  zone    Vmax    Vmin
mpc.bus = [
    001     3       0       0       0   	0       1   	1   	0	135     1       1.1 	0.9;
    002 	1       3   	0.3     0   	0   	1   	1   	0	135 	1   	1.1 	0.9;
    003 	1    	0   	0   	0   	0   	3   	1   	0	200 	1   	1.1 	0.9;
    004 	1   	0   	0   	0   	0   	3   	1   	0	200 	1   	1.1 	0.9;
    005 	1   	1   	0.5 	0   	0       2   	1   	0	135 	1   	1.1 	0.9;
    006 	2   	0   	0   	0   	0       2   	1   	0	135 	1   	1.1 	0.9
];

%% generator data
%	bus     Pg      Qg      Qmax	Qmin	Vg      mBase	status	Pmax	Pmin	Pc1	Pc2	Qc1min	Qc1max	Qc2min	Qc2max	ramp_agc	ramp_10	ramp_30	ramp_q	apf
mpc.gen = [
    001     1       0   	2       -2      1   	100 	1   	2       0   	0	0	0	0	0	0	0	0	0	0	0
    006 	1       0   	2       -2      1   	100 	1   	5       0   	0	0	0	0	0	0	0	0	0	0	0
];

%% branch data
%  fbus tbus	r	    x	    b           rateA   rateB	rateC ratio/ma  angle status angmin	angmax  PF      QF      PT      QT      MU_SF  MU_ST   MU_ANGMIN   MU_ANGMAX   VF_SET  VT_SET  TAP_MAX TAP_MIN CONV    BEQ     K2   BEQ_MIN BEQ_MAX SH_MIN  SH_MAX  GSW   ALPHA1 ALPHA2 ALPHA3      KDP  ----------------------
mpc.branch = [
    001	002 	0.001	0.10	0           100 	100 	100 	0   	0   	1	-360	360 	0   	0   	0   	0   	0       0       0           0           0       0       1       1       0       0   	1   0       0       -360    360     0       0       0       0       0;
    002	005 	0.0500	0.50 	0           100 	100 	100 	0   	0   	1	-360	360 	0   	0   	0   	0   	0   	0   	0           0       	0       0       1       1       0   	0       1   0       0       -360    360     0       0       0       0       0;
    003	002 	0.0001	0.15	0          	100 	100 	100 	1   	0   	1	-360	360 	0   	0   	0   	-0.3   	0   	0   	0           0           0       0       1.2     0.8  	1       0   	1   -0.5    0.5     -360    360     0       0.0001  0.015   0.2     0; %VSC1
    003	004 	0.05	0   	0           100 	100 	100 	0   	0   	1	-360	360 	0   	0   	0   	0   	0   	0   	0           0       	0       0       1       1       0   	0       1   0       0       -360    360     0       0       0       0       0;
    004	005 	0.0001	0.15	0       	100 	100 	100 	0   	0   	1	-360	360 	-0.5 	0   	0   	0   	0   	0   	0           0           1.1     0       1       1       2       0       1   -0.5    0.5     -50     50      0       0.0001  0.015   0.02    0; %VSC2
    006	005 	0.001	0.10	0           100 	100 	100 	0   	0   	1	-360	360 	0   	0   	0   	0   	0       0       0           0           0       0       1       1       0       0   	1   0       0       -360    360     0       0       0       0       0
];
%%-----  OPF Data  -----%%
%% generator cost data
%	1	startup	shutdown	n	x1	y1	...	xn	yn
%	2	startup	shutdown	n	c(n-1)	...	c0
mpc.gencost = [
2	0	0	3	0.02	1.0	1.0;
2	0	0	3	0.01	2.0	1.0;
2	0	0	3	0.01 	0.0	0.0;
2	0	0	3	0.01    0.0	0.0;
];

