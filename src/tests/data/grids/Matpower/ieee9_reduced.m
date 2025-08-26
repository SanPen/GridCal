function mpc = ieee9_reduced
%IEEE9_REDUCED

%% MATPOWER Case Format : Version 2
mpc.version = '2';

%%-----  Power Flow Data  -----%%
%% system MVA base
mpc.baseMVA = 100;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [
	2	2	1.02078121	0	0	10.0199383	1	1	0	345	1	1.1	0.9;
	3	2	-1.42108547e-14	0	0	0	1	1	0	345	1	1.1	0.9;
	4	1	57.9505702	0	0	33.1865451	1	1	0	345	1	1.1	0.9;
	6	1	32.0494298	0	0	37.2721303	1	1	0	345	1	1.1	0.9;
	7	1	99.5238487	35	0	26.5978631	1	1	0	345	1	1.1	0.9;
	9	1	124.45537	50	0	27.9897276	1	1	0	345	1	1.1	0.9;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin	Pc1	Pc2	Qc1min	Qc1max	Qc2min	Qc2max	ramp_agc	ramp_10	ramp_30	ramp_q	apf
mpc.gen = [
	4	67	27.03	300	-300	1.04	100	1	250	10	0	0	0	0	0	0	0	0	0	0	0;
	2	163	6.54	300	-300	1.025	100	1	300	10	0	0	0	0	0	0	0	0	0	0	0;
	3	85	-10.95	300	-300	1.025	100	1	270	10	0	0	0	0	0	0	0	0	0	0	0;
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [
	3	6	0	0.0586	0	300	300	300	0	0	1	-360	360;
	6	7	0.0119	0.1008	0	150	150	150	0	0	1	-360	360;
	9	4	0.01	0.085	0	250	250	250	0	0	1	-360	360;
	2	7	0	0.163474061	0	99999	99999	99999	1	0	1	-360	360;
	2	9	0	0.365546163	0	99999	99999	99999	1	0	1	-360	360;
	4	6	0	0.26603512	0	99999	99999	99999	1	0	1	-360	360;
	7	9	0	0.42110918	0	99999	99999	99999	1	0	1	-360	360;
];

%%-----  OPF Data  -----%%
%% generator cost data
%	1	startup	shutdown	n	x1	y1	...	xn	yn
%	2	startup	shutdown	n	c(n-1)	...	c0
mpc.gencost = [
	2	1500	0	3	0.11	5	150;
	2	2000	0	3	0.085	1.2	600;
	2	3000	0	3	0.1225	1	335;
];
