%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%                                                                  %%%%%
%%%%    IEEE PES Power Grid Library - Optimal Power Flow - v23.09     %%%%%
%%%%          (https://github.com/power-grid-lib/pglib-opf)           %%%%%
%%%%               Benchmark Group - Typical Operations               %%%%%
%%%%                         10 - May - 2019                          %%%%%
%%%%                                                                  %%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%
%   CASE5_3  Power flow data for modified 5 bus, 5 gen, 3 bus dc case based on PJM 5-bus system
%   Please see CASEFORMAT for details on the case file format.
%
%   Based on data from ...
%     F.Li and R.Bo, "Small Test Systems for Power System Economic Studies",
%     Proceedings of the 2010 IEEE Power & Energy Society General Meeting
%     and dc system form ...
%     J. Beerten, D. Van Hertem and R. Belmans, "VSC MTDC systems with a distributed DC voltage control - A power flow approach,"
%     2011 IEEE Trondheim PowerTech, Trondheim, 2011, pp. 1-6.  doi: 10.1109/PTC.2011.6019434
%
%   Created by Hakan Ergun in 2019.
%
%   Copyright (c) 2010 by The Institute of Electrical and Electronics Engineers (IEEE)
%   Licensed under the Creative Commons Attribution 4.0
%   International license, http://creativecommons.org/licenses/by/4.0/
%
%   Contact M.E. Brennan (me.brennan@ieee.org) for inquries on further reuse of
%   this dataset.

function mpc = case5_3_he()
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
	1	 2	 0.00281	 0.0281	 0.00712	 400.0	 400.0	 400.0	 0.0	 0.0	 1	 -30.0	 30.0;
	1	 4	 0.00304	 0.0304	 0.00658	 426	 426	 426	 0.0	 0.0	 1	 -30.0	 30.0;
	1	 5	 0.00064	 0.0064	 0.03126	 426	 426	 426	 0.0	 0.0	 1	 -30.0	 30.0;
	2	 3	 0.00108	 0.0108	 0.01852	 426	 426	 426	 0.0	 0.0	 1	 -30.0	 30.0;
	3	 4	 0.00297	 0.0297	 0.00674	 426	 426	 426	 0.0	 0.0	 1	 -30.0	 30.0;
	4	 5	 0.00297	 0.0297	 0.00674	 240.0	 240.0	 240.0	 0.0	 0.0	 1	 -30.0	 30.0;
];


%% dc grid topology
%colunm_names% dcpoles
mpc.dcpol=2;
% numbers of poles (1=monopolar grid, 2=bipolar grid)
%% bus data
%column_names%   busdc_i grid    Pdc     Vdc     basekVdc    Vdcmax  Vdcmin  Cdc
mpc.dcbus = [
    1              1       0       1       345         1.1     0.9     0;
    2              1       0       1       345         1.1     0.9     0;
	  3              1       0       1       345         1.1     0.9     0;
];

%% converters
%column_names%   busdc_i busac_i type_dc type_ac P_g   Q_g islcc  Vtar    rtf xtf  transformer tm   bf filter    rc      xc  reactor   basekVac    Vmmax   Vmmin   Imax    status   LossA LossB  LossCrec LossCinv  droop      Pdcset    Vdcset  dVdcset Pacmax Pacmin Qacmax Qacmin
mpc.dcconv = [
    1       2   1       1       -60    -40    0 1     0.0015  0.1121 1 1 0.0887 1 0.0001   0.16428 1  345         1.1     0.9     1.1     1       1.103 0.887  2.885    2.885      0.0050    -58.6274   1.0079   0 100 -100 50 -50;
    2       3   2       1       0       0     0 1     0.0015  0.1121 1 1 0.0887 1 0.0001   0.16428 1  345         1.1     0.9     1.1     1       1.103 0.887  2.885    2.885      0.0070     21.9013   1.0000   0 100 -100 50 -50;
    3       5   1       1       35       5    0 1     0.0015  0.1121 1 1 0.0887 1 0.0001   0.16428 1  345         1.1     0.9     1.1     1       1.103 0.887  2.885    2.885      0.0050     36.1856   0.9978   0 100 -100 50 -50;
];

%% branches
%column_names%   fbusdc  tbusdc  r      l        c   rateA   rateB   rateC   status
mpc.dcbranch = [
    1       2       0.052   0   0    100     100     100     1;
    2       3       0.052   0   0    100     100     100     1;
    1       3       0.073   0   0    100     100     100     1;
 ];

% INFO    : === Translation Options ===
% INFO    : Phase Angle Bound:           30.0 (deg.)
% INFO    : Line Capacity Model:         stat
% INFO    : Setting Flat Start
% INFO    : Line Capacity PAB:           15.0 (deg.)
% INFO    :
% INFO    : === Generator Bounds Update Notes ===
% INFO    :
% INFO    : === Base KV Replacement Notes ===
% INFO    :
% INFO    : === Transformer Setting Replacement Notes ===
% INFO    :
% INFO    : === Line Capacity Stat Model Notes ===
% INFO    : Updated Thermal Rating: on line 1-4 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 426
% INFO    : Updated Thermal Rating: on line 1-5 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 426
% INFO    : Updated Thermal Rating: on line 2-3 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 426
% INFO    : Updated Thermal Rating: on line 3-4 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 426
% INFO    :
% INFO    : === Line Capacity Monotonicity Notes ===
% INFO    :
% INFO    : === Voltage Setpoint Replacement Notes ===
% INFO    : Bus 1	: V=1.0, theta=0.0 -> V=1.0, theta=0.0
% INFO    : Bus 2	: V=1.0, theta=0.0 -> V=1.0, theta=0.0
% INFO    : Bus 3	: V=1.0, theta=0.0 -> V=1.0, theta=0.0
% INFO    : Bus 4	: V=1.0, theta=0.0 -> V=1.0, theta=0.0
% INFO    : Bus 5	: V=1.0, theta=0.0 -> V=1.0, theta=0.0
% INFO    :
% INFO    : === Generator Setpoint Replacement Notes ===
% INFO    : Gen at bus 1	: Pg=40.0, Qg=0.0 -> Pg=20.0, Qg=0.0
% INFO    : Gen at bus 1	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 1	: Pg=170.0, Qg=0.0 -> Pg=85.0, Qg=0.0
% INFO    : Gen at bus 1	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 3	: Pg=323.49, Qg=0.0 -> Pg=260.0, Qg=0.0
% INFO    : Gen at bus 3	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 4	: Pg=0.0, Qg=0.0 -> Pg=100.0, Qg=0.0
% INFO    : Gen at bus 4	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 5	: Pg=466.51, Qg=0.0 -> Pg=300.0, Qg=0.0
% INFO    : Gen at bus 5	: Vg=1.0 -> Vg=1.0
% INFO    :
% INFO    : === Writing Matpower Case File Notes ===
