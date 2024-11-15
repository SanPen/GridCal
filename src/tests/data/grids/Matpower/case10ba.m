function mpc = case10ba
%CASE10BA  Power flow data for 10 bus distribution system from Baghzouz & Ertem
%   Please see CASEFORMAT for details on the case file format.
%
%   Data from ...
%       Baghzouz Y, Ertem S., "Shunt capacitor sizing for radial
%       distribution feeders with distorted substation voltages",
%       IEEE Trans. Power Deliv., vol.5, 1990, pp. 650-657.

%% MATPOWER Case Format : Version 2
mpc.version = '2';

%%-----  Power Flow Data  -----%%
%% system MVA base
mpc.baseMVA = 10;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [ %% (Pd and Qd are specified in kW & kVAr here, converted to MW & MVAr below)
	1	3	0	0	0	0	1	1	0	23	1	1	1;
	2	1	1840	460	0	0	1	1	0	23	1	1.1	0.9;
	3	1	980	340	0	0	1	1	0	23	1	1.1	0.9;
	4	1	1790	446	0	0	1	1	0	23	1	1.1	0.9;
	5	1	1598	1840	0	0	1	1	0	23	1	1.1	0.9;
	6	1	1610	600	0	0	1	1	0	23	1	1.1	0.9;
	7	1	780	110	0	0	1	1	0	23	1	1.1	0.9;
	8	1	1150	60	0	0	1	1	0	23	1	1.1	0.9;
	9	1	980	130	0	0	1	1	0	23	1	1.1	0.9;
	10	1	1640	200	0	0	1	1	0	23	1	1.1	0.9;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin	Pc1	Pc2	Qc1min	Qc1max	Qc2min	Qc2max	ramp_agc	ramp_10	ramp_30	ramp_q	apf
mpc.gen = [
	1	0	0	10	-10	1	100	1	10	0	0	0	0	0	0	0	0	0	0	0	0;
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [  %% (r and x specified in ohms here, converted to p.u. below)
	1	2	0.1233	0.4127	0	0	0	0	0	0	1	-360	360;
	2	3	0.014	0.6051	0	0	0	0	0	0	1	-360	360;
	3	4	0.7463	1.205	0	0	0	0	0	0	1	-360	360;
	4	5	0.6984	0.6084	0	0	0	0	0	0	1	-360	360;
	5	6	1.9831	1.7276	0	0	0	0	0	0	1	-360	360;
	6	7	0.9053	0.7886	0	0	0	0	0	0	1	-360	360;
	7	8	2.0552	1.164	0	0	0	0	0	0	1	-360	360;
	8	9	4.7953	2.716	0	0	0	0	0	0	1	-360	360;
	9	10	5.3434	3.0264	0	0	0	0	0	0	1	-360	360;
];

%%-----  OPF Data  -----%%
%% generator cost data
%	1	startup	shutdown	n	x1	y1	...	xn	yn
%	2	startup	shutdown	n	c(n-1)	...	c0
mpc.gencost = [
	2	0	0	3	0	20	0;
];


%% convert branch impedances from Ohms to p.u.
[PQ, PV, REF, NONE, BUS_I, BUS_TYPE, PD, QD, GS, BS, BUS_AREA, VM, ...
    VA, BASE_KV, ZONE, VMAX, VMIN, LAM_P, LAM_Q, MU_VMAX, MU_VMIN] = idx_bus;
[F_BUS, T_BUS, BR_R, BR_X, BR_B, RATE_A, RATE_B, RATE_C, ...
    TAP, SHIFT, BR_STATUS, PF, QF, PT, QT, MU_SF, MU_ST, ...
    ANGMIN, ANGMAX, MU_ANGMIN, MU_ANGMAX] = idx_brch;
Vbase = mpc.bus(1, BASE_KV) * 1e3;      %% in Volts
Sbase = mpc.baseMVA * 1e6;              %% in VA
mpc.branch(:, [BR_R BR_X]) = mpc.branch(:, [BR_R BR_X]) / (Vbase^2 / Sbase);

%% convert loads from kW to MW
mpc.bus(:, [PD, QD]) = mpc.bus(:, [PD, QD]) / 1e3;
