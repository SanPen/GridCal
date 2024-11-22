function mpc = case28da
%CASE28DA Power flow data for 28 bus distribution system from Das, et al
%   Please see CASEFORMAT for details on the case file format.
%
%   Data from ...
%       D. Das, H.S. Nagi, D.P. Kothari, "Novel method for solving radial
%       distribution networks", IEE Proc. C, Vol. 141, No. 4, pp. 291-298,
%       1994.

%% MATPOWER Case Format : Version 2
mpc.version = '2';

%%-----  Power Flow Data  -----%%
%% system MVA base
mpc.baseMVA = 1;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [ %% (Pd and Qd are specified in kW & kVAr here, converted to MW & MVAr below)
	1	3	0	0	0	0	1	1	0	11	1	1	1;
	2	1	35.28	35.993	0	0	1	1	0	11	1	1	1;
	3	1	14	14.283	0	0	1	1	0	11	1	1	1;
	4	1	35.28	35.993	0	0	1	1	0	11	1	1	1;
	5	1	14	14.283	0	0	1	1	0	11	1	1	1;
	6	1	35.28	35.993	0	0	1	1	0	11	1	1	1;
	7	1	35.28	35.993	0	0	1	1	0	11	1	1	1;
	8	1	35.28	35.993	0	0	1	1	0	11	1	1	1;
	9	1	14	14.283	0	0	1	1	0	11	1	1	1;
	10	1	14	14.283	0	0	1	1	0	11	1	1	1;
	11	1	56	57.131	0	0	1	1	0	11	1	1	1;
	12	1	35.28	35.993	0	0	1	1	0	11	1	1	1;
	13	1	35.28	35.993	0	0	1	1	0	11	1	1	1;
	14	1	14	14.283	0	0	1	1	0	11	1	1	1;
	15	1	35.28	35.993	0	0	1	1	0	11	1	1	1;
	16	1	35.28	35.993	0	0	1	1	0	11	1	1	1;
	17	1	8.96	9.141	0	0	1	1	0	11	1	1	1;
	18	1	8.96	9.141	0	0	1	1	0	11	1	1	1;
	19	1	35.28	35.993	0	0	1	1	0	11	1	1	1;
	20	1	35.28	35.993	0	0	1	1	0	11	1	1	1;
	21	1	14	14.283	0	0	1	1	0	11	1	1	1;
	22	1	35.28	35.993	0	0	1	1	0	11	1	1	1;
	23	1	8.96	9.141	0	0	1	1	0	11	1	1	1;
	24	1	56	57.131	0	0	1	1	0	11	1	1	1;
	25	1	8.96	9.141	0	0	1	1	0	11	1	1	1;
	26	1	35.28	35.993	0	0	1	1	0	11	1	1	1;
	27	1	35.28	35.993	0	0	1	1	0	11	1	1	1;
	28	1	35.28	35.993	0	0	1	1	0	11	1	1	1;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin	Pc1	Pc2	Qc1min	Qc1max	Qc2min	Qc2max	ramp_agc	ramp_10	ramp_30	ramp_q	apf
mpc.gen = [
	1	0	0	10	-10	1	100	1	10	0	0	0	0	0	0	0	0	0	0	0	0;
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [  %% (r and x specified in ohms here, converted to p.u. below)
	1	2	1.197	0.82	0	0	0	0	0	0	1	-360	360;
	2	3	1.796	1.231	0	0	0	0	0	0	1	-360	360;
	3	4	1.306	0.895	0	0	0	0	0	0	1	-360	360;
	4	5	1.851	1.268	0	0	0	0	0	0	1	-360	360;
	5	6	1.524	1.044	0	0	0	0	0	0	1	-360	360;
	6	7	1.905	1.305	0	0	0	0	0	0	1	-360	360;
	7	8	1.197	0.82	0	0	0	0	0	0	1	-360	360;
	8	9	0.653	0.447	0	0	0	0	0	0	1	-360	360;
	9	10	1.143	0.783	0	0	0	0	0	0	1	-360	360;
	4	11	2.823	1.172	0	0	0	0	0	0	1	-360	360;
	11	12	1.184	0.491	0	0	0	0	0	0	1	-360	360;
	12	13	1.002	0.416	0	0	0	0	0	0	1	-360	360;
	13	14	0.455	0.189	0	0	0	0	0	0	1	-360	360;
	14	15	0.546	0.227	0	0	0	0	0	0	1	-360	360;
	5	16	2.55	1.058	0	0	0	0	0	0	1	-360	360;
	6	17	1.366	0.567	0	0	0	0	0	0	1	-360	360;
	17	18	0.819	0.34	0	0	0	0	0	0	1	-360	360;
	18	19	1.548	0.642	0	0	0	0	0	0	1	-360	360;
	19	20	1.366	0.567	0	0	0	0	0	0	1	-360	360;
	20	21	3.552	1.474	0	0	0	0	0	0	1	-360	360;
	7	22	1.548	0.642	0	0	0	0	0	0	1	-360	360;
	22	23	1.092	0.453	0	0	0	0	0	0	1	-360	360;
	23	24	0.91	0.378	0	0	0	0	0	0	1	-360	360;
	24	25	0.455	0.189	0	0	0	0	0	0	1	-360	360;
	25	26	0.364	0.151	0	0	0	0	0	0	1	-360	360;
	8	27	0.546	0.226	0	0	0	0	0	0	1	-360	360;
	27	28	0.273	0.113	0	0	0	0	0	0	1	-360	360;
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
