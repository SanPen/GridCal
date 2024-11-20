function mpc = case12da
%CASE12DA  Power flow data for 12 bus distribution system from Das, et al
%   Please see CASEFORMAT for details on the case file format.
%
%   Data from ...
%       D. Das, H.S. Nagi, D.P. Kothari, "Novel method for solving radial
%       distribution networks", IEE Proc. C, Vol. 141, No. 4, pp. 291-298, 1994.

%% MATPOWER Case Format : Version 2
mpc.version = '2';

%%-----  Power Flow Data  -----%%
%% system MVA base
mpc.baseMVA = 1;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [ %% (Pd and Qd are specified in kW & kVAr here, converted to MW & MVAr below)
	1	3	0	0	0	0	1	1	0	11	1	1	1;
	2	1	60	60	0	0	1	1	0	11	1	1.1	0.9;
	3	1	40	30	0	0	1	1	0	11	1	1.1	0.9;
	4	1	55	55	0	0	1	1	0	11	1	1.1	0.9;
	5	1	30	30	0	0	1	1	0	11	1	1.1	0.9;
	6	1	20	15	0	0	1	1	0	11	1	1.1	0.9;
	7	1	55	55	0	0	1	1	0	11	1	1.1	0.9;
	8	1	45	45	0	0	1	1	0	11	1	1.1	0.9;
	9	1	40	40	0	0	1	1	0	11	1	1.1	0.9;
	10	1	35	30	0	0	1	1	0	11	1	1.1	0.9;
	11	1	40	30	0	0	1	1	0	11	1	1.1	0.9;
	12	1	15	15	0	0	1	1	0	11	1	1.1	0.9;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin	Pc1	Pc2	Qc1min	Qc1max	Qc2min	Qc2max	ramp_agc	ramp_10	ramp_30	ramp_q	apf
mpc.gen = [
	1	0	0	10	-10	1	100	1	10	0	0	0	0	0	0	0	0	0	0	0	0;
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [  %% (r and x specified in ohms here, converted to p.u. below)
	1	2	1.093	0.455	0	0	0	0	0	0	1	-360	360;
	2	3	1.184	0.494	0	0	0	0	0	0	1	-360	360;
	3	4	2.095	0.873	0	0	0	0	0	0	1	-360	360;
	4	5	3.188	1.329	0	0	0	0	0	0	1	-360	360;
	5	6	1.093	0.455	0	0	0	0	0	0	1	-360	360;
	6	7	1.002	0.417	0	0	0	0	0	0	1	-360	360;
	7	8	4.403	1.215	0	0	0	0	0	0	1	-360	360;
	8	9	5.642	1.597	0	0	0	0	0	0	1	-360	360;
	9	10	2.89	0.818	0	0	0	0	0	0	1	-360	360;
	10	11	1.514	0.428	0	0	0	0	0	0	1	-360	360;
	11	12	1.238	0.351	0	0	0	0	0	0	1	-360	360;
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
