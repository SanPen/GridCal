%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%                                                                  %%%%%
%%%%    IEEE PES Power Grid Library - Optimal Power Flow - v23.07     %%%%%
%%%%          (https://github.com/power-grid-lib/pglib-opf)           %%%%%
%%%%             Benchmark Group - Active Power Increase              %%%%%
%%%%                         23 - July - 2023                         %%%%%
%%%%                                                                  %%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
function mpc = pglib_opf_case14_ieee__api
mpc.version = '2';
mpc.baseMVA = 100.0;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [
	1	 3	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	2	 2	 42.66	 12.70	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	3	 2	 185.17	 19.00	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	4	 1	 47.80	 -3.90	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	5	 1	 14.94	 1.60	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	6	 2	 22.02	 7.50	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	7	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	8	 2	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	9	 1	 57.99	 16.60	 0.0	 19.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	10	 1	 17.69	 5.80	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	11	 1	 6.88	 1.80	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	12	 1	 11.99	 1.60	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	13	 1	 26.54	 5.80	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	14	 1	 29.29	 5.00	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin
mpc.gen = [
	1	 199.0	 0.0	 199.0	 -199.0	 1.0	 100.0	 1	 398	 0.0; % NG
	2	 115.0	 0.0	 115.0	 -115.0	 1.0	 100.0	 1	 230	 0.0; % NG
	3	 0.0	 0.0	 72.0	 -72.0	 1.0	 100.0	 1	 0	 0.0; % SYNC
	6	 0.0	 0.0	 57.6	 -57.6	 1.0	 100.0	 1	 0	 0.0; % SYNC
	8	 0.0	 0.0	 30.0	 -30.0	 1.0	 100.0	 1	 0	 0.0; % SYNC
];

%% generator cost data
%	2	startup	shutdown	n	c(n-1)	...	c0
mpc.gencost = [
	2	 0.0	 0.0	 3	   0.000000	   7.920951	   0.000000; % NG
	2	 0.0	 0.0	 3	   0.000000	  23.269494	   0.000000; % NG
	2	 0.0	 0.0	 3	   0.000000	   0.000000	   0.000000; % SYNC
	2	 0.0	 0.0	 3	   0.000000	   0.000000	   0.000000; % SYNC
	2	 0.0	 0.0	 3	   0.000000	   0.000000	   0.000000; % SYNC
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [
	1	 2	 0.01938	 0.05917	 0.0528	 472.0	 472.0	 472.0	 0.0	 0.0	 1	 -30.0	 30.0;
	1	 5	 0.05403	 0.22304	 0.0492	 128.0	 128.0	 128.0	 0.0	 0.0	 1	 -30.0	 30.0;
	2	 3	 0.04699	 0.19797	 0.0438	 145.0	 145.0	 145.0	 0.0	 0.0	 1	 -30.0	 30.0;
	2	 4	 0.05811	 0.17632	 0.034	 158.0	 158.0	 158.0	 0.0	 0.0	 1	 -30.0	 30.0;
	2	 5	 0.05695	 0.17388	 0.0346	 161.0	 161.0	 161.0	 0.0	 0.0	 1	 -30.0	 30.0;
	3	 4	 0.06701	 0.17103	 0.0128	 160.0	 160.0	 160.0	 0.0	 0.0	 1	 -30.0	 30.0;
	4	 5	 0.01335	 0.04211	 0.0	 664.0	 664.0	 664.0	 0.0	 0.0	 1	 -30.0	 30.0;
	4	 7	 0.0	 0.20912	 0.0	 141.0	 141.0	 141.0	 0.978	 0.0	 1	 -30.0	 30.0;
	4	 9	 0.0	 0.55618	 0.0	 53.0	 53.0	 53.0	 0.969	 0.0	 1	 -30.0	 30.0;
	5	 6	 0.0	 0.25202	 0.0	 117.0	 117.0	 117.0	 0.932	 0.0	 1	 -30.0	 30.0;
	6	 11	 0.09498	 0.1989	 0.0	 134.0	 134.0	 134.0	 0.0	 0.0	 1	 -30.0	 30.0;
	6	 12	 0.12291	 0.25581	 0.0	 104.0	 104.0	 104.0	 0.0	 0.0	 1	 -30.0	 30.0;
	6	 13	 0.06615	 0.13027	 0.0	 201.0	 201.0	 201.0	 0.0	 0.0	 1	 -30.0	 30.0;
	7	 8	 0.0	 0.17615	 0.0	 167.0	 167.0	 167.0	 0.0	 0.0	 1	 -30.0	 30.0;
	7	 9	 0.0	 0.11001	 0.0	 267.0	 267.0	 267.0	 0.0	 0.0	 1	 -30.0	 30.0;
	9	 10	 0.03181	 0.0845	 0.0	 325.0	 325.0	 325.0	 0.0	 0.0	 1	 -30.0	 30.0;
	9	 14	 0.12711	 0.27038	 0.0	 99.0	 99.0	 99.0	 0.0	 0.0	 1	 -30.0	 30.0;
	10	 11	 0.08205	 0.19207	 0.0	 141.0	 141.0	 141.0	 0.0	 0.0	 1	 -30.0	 30.0;
	12	 13	 0.22092	 0.19988	 0.0	 99.0	 99.0	 99.0	 0.0	 0.0	 1	 -30.0	 30.0;
	13	 14	 0.17093	 0.34802	 0.0	 76.0	 76.0	 76.0	 0.0	 0.0	 1	 -30.0	 30.0;
];

% INFO    : === Translation Options ===
% INFO    : Load Model:                  from file ./pglib_opf_case14_ieee.m.api.sol
% INFO    : Gen Active Capacity Model:   stat
% INFO    : Gen Reactive Capacity Model: al50ag
% INFO    : Gen Active Cost Model:       stat
% INFO    : 
% INFO    : === Load Replacement Notes ===
% INFO    : Bus 2	: Pd=21.7, Qd=12.7 -> Pd=42.66, Qd=12.70
% INFO    : Bus 3	: Pd=94.2, Qd=19.0 -> Pd=185.17, Qd=19.00
% INFO    : Bus 4	: Pd=47.8, Qd=-3.9 -> Pd=47.80, Qd=-3.90
% INFO    : Bus 5	: Pd=7.6, Qd=1.6 -> Pd=14.94, Qd=1.60
% INFO    : Bus 6	: Pd=11.2, Qd=7.5 -> Pd=22.02, Qd=7.50
% INFO    : Bus 9	: Pd=29.5, Qd=16.6 -> Pd=57.99, Qd=16.60
% INFO    : Bus 10	: Pd=9.0, Qd=5.8 -> Pd=17.69, Qd=5.80
% INFO    : Bus 11	: Pd=3.5, Qd=1.8 -> Pd=6.88, Qd=1.80
% INFO    : Bus 12	: Pd=6.1, Qd=1.6 -> Pd=11.99, Qd=1.60
% INFO    : Bus 13	: Pd=13.5, Qd=5.8 -> Pd=26.54, Qd=5.80
% INFO    : Bus 14	: Pd=14.9, Qd=5.0 -> Pd=29.29, Qd=5.00
% INFO    : 
% INFO    : === Generator Setpoint Replacement Notes ===
% INFO    : Gen at bus 1	: Pg=170.0, Qg=5.0 -> Pg=353.0, Qg=37.0
% INFO    : Gen at bus 2	: Pg=29.5, Qg=0.0 -> Pg=153.0, Qg=41.0
% INFO    : Gen at bus 3	: Pg=0.0, Qg=20.0 -> Pg=0.0, Qg=60.0
% INFO    : Gen at bus 6	: Pg=0.0, Qg=9.0 -> Pg=0.0, Qg=48.0
% INFO    : Gen at bus 8	: Pg=0.0, Qg=9.0 -> Pg=0.0, Qg=25.0
% INFO    : 
% INFO    : === Generator Reactive Capacity Atleast Setpoint Value Notes ===
% INFO    : Gen at bus 1	: Qg 37.0, Qmin 0.0, Qmax 10.0 -> Qmin -44.4, Qmax 44.4
% INFO    : Gen at bus 2	: Qg 41.0, Qmin -30.0, Qmax 30.0 -> Qmin -49.2, Qmax 49.2
% INFO    : Gen at bus 3	: Qg 60.0, Qmin 0.0, Qmax 40.0 -> Qmin -72.0, Qmax 72.0
% INFO    : Gen at bus 6	: Qg 48.0, Qmin -6.0, Qmax 24.0 -> Qmin -57.6, Qmax 57.6
% INFO    : Gen at bus 8	: Qg 25.0, Qmin -6.0, Qmax 24.0 -> Qmin -30.0, Qmax 30.0
% INFO    : 
% INFO    : === Generator Classification Notes ===
% INFO    : SYNC   3   -     0.00
% INFO    : NG     2   -   100.00
% INFO    : 
% INFO    : === Generator Active Capacity Stat Model Notes ===
% INFO    : Gen at bus 1 - NG	: Pg=353.0, Pmax=340.0 -> Pmax=398   samples: 10
% INFO    : Gen at bus 2 - NG	: Pg=153.0, Pmax=59.0 -> Pmax=230   samples: 1
% INFO    : Gen at bus 3 - SYNC	: Pg=0.0, Pmax=0.0 -> Pmax=0   samples: 0
% INFO    : Gen at bus 6 - SYNC	: Pg=0.0, Pmax=0.0 -> Pmax=0   samples: 0
% INFO    : Gen at bus 8 - SYNC	: Pg=0.0, Pmax=0.0 -> Pmax=0   samples: 0
% INFO    : 
% INFO    : === Generator Active Capacity LB Model Notes ===
% INFO    : 
% INFO    : === Generator Reactive Capacity Atleast Max 50 Percent Active Model Notes ===
% INFO    : Gen at bus 1 - NG	: Pmax 398.0, Qmin -44.4, Qmax 44.4 -> Qmin -199.0, Qmax 199.0
% INFO    : Gen at bus 2 - NG	: Pmax 230.0, Qmin -49.2, Qmax 49.2 -> Qmin -115.0, Qmax 115.0
% INFO    : 
% INFO    : === Generator Setpoint Replacement Notes ===
% INFO    : Gen at bus 1	: Pg=353.0, Qg=37.0 -> Pg=199.0, Qg=0.0
% INFO    : Gen at bus 1	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 2	: Pg=153.0, Qg=41.0 -> Pg=115.0, Qg=0.0
% INFO    : Gen at bus 2	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 3	: Pg=0.0, Qg=60.0 -> Pg=0.0, Qg=0.0
% INFO    : Gen at bus 3	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 6	: Pg=0.0, Qg=48.0 -> Pg=0.0, Qg=0.0
% INFO    : Gen at bus 6	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 8	: Pg=0.0, Qg=25.0 -> Pg=0.0, Qg=0.0
% INFO    : Gen at bus 8	: Vg=1.0 -> Vg=1.0
% INFO    : 
% INFO    : === Writing Matpower Case File Notes ===
