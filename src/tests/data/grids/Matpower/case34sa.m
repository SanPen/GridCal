function mpc = case34sa
%CASE34SA  Power flow data for 18 bus distribution system from Salama & Chikhani
%   Please see CASEFORMAT for details on the case file format.
%
%   Data from ...
%       Salama MMA, Chikhani AY (1993) Simplified network approach to the var
%       control problem for radial distribution systems. IEEE Trans Power
%       Deliv 8:1529-1535. doi: 10.1109/61.252679
%       URL: https://doi.org/10.1109/61.252679

%% MATPOWER Case Format : Version 2
mpc.version = '2';

%%-----  Power Flow Data  -----%%
%% system MVA base
mpc.baseMVA = 1;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [ %% (Pd and Qd are specified in kW & kVAr here, converted to MW & MVAr below)
	1	3	0	0	0	0	1	1	0	11	1	1	1;
	2	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	3	1	0	0	0	0	1	1	0	11	1	1.1	0.9;
	4	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	5	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	6	1	0	0	0	0	1	1	0	11	1	1.1	0.9;
	7	1	0	0	0	0	1	1	0	11	1	1.1	0.9;
	8	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	9	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	10	1	0	0	0	0	1	1	0	11	1	1.1	0.9;
	11	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	12	1	84	137	0	0	1	1	0	11	1	1.1	0.9;
	13	1	45	72	0	0	1	1	0	11	1	1.1	0.9;
	14	1	45	72	0	0	1	1	0	11	1	1.1	0.9;
	15	1	45	72	0	0	1	1	0	11	1	1.1	0.9;
	16	1	7.5	13.5	0	0	1	1	0	11	1	1.1	0.9;
	17	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	18	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	19	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	20	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	21	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	22	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	23	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	24	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	25	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	26	1	142.5	230	0	0	1	1	0	11	1	1.1	0.9;
	27	1	85	137	0	0	1	1	0	11	1	1.1	0.9;
	28	1	48	75	0	0	1	1	0	11	1	1.1	0.9;
	29	1	48	75	0	0	1	1	0	11	1	1.1	0.9;
	30	1	48	75	0	0	1	1	0	11	1	1.1	0.9;
	31	1	34.5	57	0	0	1	1	0	11	1	1.1	0.9;
	32	1	34.5	57	0	0	1	1	0	11	1	1.1	0.9;
	33	1	34.5	57	0	0	1	1	0	11	1	1.1	0.9;
	34	1	34.5	57	0	0	1	1	0	11	1	1.1	0.9;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin	Pc1	Pc2	Qc1min	Qc1max	Qc2min	Qc2max	ramp_agc	ramp_10	ramp_30	ramp_q	apf
mpc.gen = [
	1	0	0	10	-10	1	100	1	10	0	0	0	0	0	0	0	0	0	0	0	0;
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [  %% (r and x specified in ohms here, converted to p.u. below)
	1	2	0.117	0.048	0	0	0	0	0	0	1	-360	360;
	2	3	0.10725	0.044	0	0	0	0	0	0	1	-360	360;
	3	4	0.16445	0.04565	0	0	0	0	0	0	1	-360	360;
	4	5	0.1495	0.0415	0	0	0	0	0	0	1	-360	360;
	5	6	0.1495	0.0415	0	0	0	0	0	0	1	-360	360;
	6	7	0.3144	0.054	0	0	0	0	0	0	1	-360	360;
	7	8	0.2096	0.036	0	0	0	0	0	0	1	-360	360;
	8	9	0.3144	0.054	0	0	0	0	0	0	1	-360	360;
	9	10	0.2096	0.036	0	0	0	0	0	0	1	-360	360;
	10	11	0.131	0.0225	0	0	0	0	0	0	1	-360	360;
	11	12	0.1048	0.018	0	0	0	0	0	0	1	-360	360;
	3	13	0.1572	0.027	0	0	0	0	0	0	1	-360	360;
	13	14	0.2096	0.036	0	0	0	0	0	0	1	-360	360;
	14	15	0.1048	0.018	0	0	0	0	0	0	1	-360	360;
	15	16	0.0524	0.009	0	0	0	0	0	0	1	-360	360;
	6	17	0.1794	0.0498	0	0	0	0	0	0	1	-360	360;
	17	18	0.16445	0.04565	0	0	0	0	0	0	1	-360	360;
	18	19	0.2079	0.0473	0	0	0	0	0	0	1	-360	360;
	19	20	0.189	0.043	0	0	0	0	0	0	1	-360	360;
	20	21	0.189	0.043	0	0	0	0	0	0	1	-360	360;
	21	22	0.262	0.045	0	0	0	0	0	0	1	-360	360;
	22	23	0.262	0.045	0	0	0	0	0	0	1	-360	360;
	23	24	0.3144	0.054	0	0	0	0	0	0	1	-360	360;
	24	25	0.2096	0.036	0	0	0	0	0	0	1	-360	360;
	25	26	0.131	0.0225	0	0	0	0	0	0	1	-360	360;
	26	27	0.1048	0.018	0	0	0	0	0	0	1	-360	360;
	7	28	0.1572	0.027	0	0	0	0	0	0	1	-360	360;
	28	29	0.1572	0.027	0	0	0	0	0	0	1	-360	360;
	29	30	0.1572	0.027	0	0	0	0	0	0	1	-360	360;
	10	31	0.1572	0.027	0	0	0	0	0	0	1	-360	360;
	31	32	0.2096	0.036	0	0	0	0	0	0	1	-360	360;
	32	33	0.1572	0.027	0	0	0	0	0	0	1	-360	360;
	33	34	0.1048	0.018	0	0	0	0	0	0	1	-360	360;
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
