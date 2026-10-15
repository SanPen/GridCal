%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%                                                                  %%%%%
%%%%    IEEE PES Power Grid Library - Optimal Power Flow - v23.07     %%%%%
%%%%          (https://github.com/power-grid-lib/pglib-opf)           %%%%%
%%%%             Benchmark Group - Small Angle Difference             %%%%%
%%%%                         23 - July - 2023                         %%%%%
%%%%                                                                  %%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
function mpc = pglib_opf_case5_pjm__sad
mpc.version = '2';
mpc.baseMVA = 100.0;

%% area data
%	area	refbus
mpc.areas = [
	1	 4;
];

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [
	1	 2	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 230.0	 1	    1.10000	    0.90000;
	2	 1	 300.0	 98.61	 0.0	 0.0	 1	    1.00000	    0.00000	 230.0	 1	    1.10000	    0.90000;
	3	 2	 300.0	 98.61	 0.0	 0.0	 1	    1.00000	    0.00000	 230.0	 1	    1.10000	    0.90000;
	4	 3	 400.0	 131.47	 0.0	 0.0	 1	    1.00000	    0.00000	 230.0	 1	    1.10000	    0.90000;
	5	 2	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 230.0	 1	    1.10000	    0.90000;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin
mpc.gen = [
	1	 20.0	 0.0	 30.0	 -30.0	 1.0	 100.0	 1	 40.0	 0.0;
	1	 85.0	 0.0	 127.5	 -127.5	 1.0	 100.0	 1	 170.0	 0.0;
	3	 260.0	 0.0	 390.0	 -390.0	 1.0	 100.0	 1	 520.0	 0.0;
	4	 100.0	 0.0	 150.0	 -150.0	 1.0	 100.0	 1	 200.0	 0.0;
	5	 300.0	 0.0	 450.0	 -450.0	 1.0	 100.0	 1	 600.0	 0.0;
];

%% generator cost data
%	2	startup	shutdown	n	c(n-1)	...	c0
mpc.gencost = [
	2	 0.0	 0.0	 3	   0.000000	  14.000000	   0.000000;
	2	 0.0	 0.0	 3	   0.000000	  15.000000	   0.000000;
	2	 0.0	 0.0	 3	   0.000000	  30.000000	   0.000000;
	2	 0.0	 0.0	 3	   0.000000	  40.000000	   0.000000;
	2	 0.0	 0.0	 3	   0.000000	  10.000000	   0.000000;
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [
	1	 2	 0.00281	 0.0281	 0.00712	 400.0	 400.0	 400.0	 0.0	 0.0	 1	 -1.33164584752	 1.33164584752;
	1	 4	 0.00304	 0.0304	 0.00658	 426.0	 426.0	 426.0	 0.0	 0.0	 1	 -1.33164584752	 1.33164584752;
	1	 5	 0.00064	 0.0064	 0.03126	 426.0	 426.0	 426.0	 0.0	 0.0	 1	 -1.33164584752	 1.33164584752;
	2	 3	 0.00108	 0.0108	 0.01852	 426.0	 426.0	 426.0	 0.0	 0.0	 1	 -1.33164584752	 1.33164584752;
	3	 4	 0.00297	 0.0297	 0.00674	 426.0	 426.0	 426.0	 0.0	 0.0	 1	 -1.33164584752	 1.33164584752;
	4	 5	 0.00297	 0.0297	 0.00674	 240.0	 240.0	 240.0	 0.0	 0.0	 1	 -1.33164584752	 1.33164584752;
];

% INFO    : === Translation Options ===
% INFO    : Phase Angle Bound:           1.33164584752 (deg.)
% INFO    : 
% INFO    : === Generator Bounds Update Notes ===
% INFO    : 
% INFO    : === Base KV Replacement Notes ===
% INFO    : 
% INFO    : === Transformer Setting Replacement Notes ===
% INFO    : 
% INFO    : === Line Capacity Monotonicity Notes ===
% INFO    : 
% INFO    : === Writing Matpower Case File Notes ===
