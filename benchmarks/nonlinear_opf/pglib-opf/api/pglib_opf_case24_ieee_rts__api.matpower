%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%                                                                  %%%%%
%%%%    IEEE PES Power Grid Library - Optimal Power Flow - v23.07     %%%%%
%%%%          (https://github.com/power-grid-lib/pglib-opf)           %%%%%
%%%%             Benchmark Group - Active Power Increase              %%%%%
%%%%                         23 - July - 2023                         %%%%%
%%%%                                                                  %%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
function mpc = pglib_opf_case24_ieee_rts__api
mpc.version = '2';
mpc.baseMVA = 100.0;

%% area data
%	area	refbus
mpc.areas = [
	1	 1;
	2	 3;
	3	 8;
	4	 6;
];

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [
	1	 2	 207.30	 22.00	 0.0	 0.0	 1	    1.00000	    0.00000	 138.0	 1	    1.05000	    0.95000;
	2	 2	 186.19	 20.00	 0.0	 0.0	 1	    1.00000	    0.00000	 138.0	 1	    1.05000	    0.95000;
	3	 1	 345.50	 37.00	 0.0	 0.0	 1	    1.00000	    0.00000	 138.0	 1	    1.05000	    0.95000;
	4	 1	 142.04	 15.00	 0.0	 0.0	 1	    1.00000	    0.00000	 138.0	 1	    1.05000	    0.95000;
	5	 1	 136.28	 14.00	 0.0	 0.0	 1	    1.00000	    0.00000	 138.0	 1	    1.05000	    0.95000;
	6	 1	 261.05	 28.00	 0.0	 -100.0	 2	    1.00000	    0.00000	 138.0	 1	    1.05000	    0.95000;
	7	 2	 239.93	 25.00	 0.0	 0.0	 2	    1.00000	    0.00000	 138.0	 1	    1.05000	    0.95000;
	8	 1	 328.23	 35.00	 0.0	 0.0	 2	    1.00000	    0.00000	 138.0	 1	    1.05000	    0.95000;
	9	 1	 335.90	 36.00	 0.0	 0.0	 1	    1.00000	    0.00000	 138.0	 1	    1.05000	    0.95000;
	10	 1	 374.29	 40.00	 0.0	 0.0	 2	    1.00000	    0.00000	 138.0	 1	    1.05000	    0.95000;
	11	 1	 0.0	 0.0	 0.0	 0.0	 3	    1.00000	    0.00000	 230.0	 1	    1.05000	    0.95000;
	12	 1	 0.0	 0.0	 0.0	 0.0	 3	    1.00000	    0.00000	 230.0	 1	    1.05000	    0.95000;
	13	 3	 508.66	 54.00	 0.0	 0.0	 3	    1.00000	    0.00000	 230.0	 1	    1.05000	    0.95000;
	14	 2	 372.37	 39.00	 0.0	 0.0	 3	    1.00000	    0.00000	 230.0	 1	    1.05000	    0.95000;
	15	 2	 608.47	 64.00	 0.0	 0.0	 4	    1.00000	    0.00000	 230.0	 1	    1.05000	    0.95000;
	16	 2	 191.95	 20.00	 0.0	 0.0	 4	    1.00000	    0.00000	 230.0	 1	    1.05000	    0.95000;
	17	 1	 0.0	 0.0	 0.0	 0.0	 4	    1.00000	    0.00000	 230.0	 1	    1.05000	    0.95000;
	18	 2	 639.18	 68.00	 0.0	 0.0	 4	    1.00000	    0.00000	 230.0	 1	    1.05000	    0.95000;
	19	 1	 347.42	 37.00	 0.0	 0.0	 3	    1.00000	    0.00000	 230.0	 1	    1.05000	    0.95000;
	20	 1	 245.69	 26.00	 0.0	 0.0	 3	    1.00000	    0.00000	 230.0	 1	    1.05000	    0.95000;
	21	 2	 0.0	 0.0	 0.0	 0.0	 4	    1.00000	    0.00000	 230.0	 1	    1.05000	    0.95000;
	22	 2	 0.0	 0.0	 0.0	 0.0	 4	    1.00000	    0.00000	 230.0	 1	    1.05000	    0.95000;
	23	 2	 0.0	 0.0	 0.0	 0.0	 3	    1.00000	    0.00000	 230.0	 1	    1.05000	    0.95000;
	24	 1	 0.0	 0.0	 0.0	 0.0	 4	    1.00000	    0.00000	 230.0	 1	    1.05000	    0.95000;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin
mpc.gen = [
	1	 43.5	 0.0	 40.0	 -40.0	 1.0	 100.0	 1	 79	 8.0; % PEL
	1	 109.5	 0.0	 106.0	 -106.0	 1.0	 100.0	 1	 211	 8.0; % PEL
	1	 41.3	 0.0	 38.0	 -38.0	 1.0	 100.0	 1	 75	 7.6; % PEL
	1	 42.8	 0.0	 39.0	 -39.0	 1.0	 100.0	 1	 78	 7.6; % NG
	2	 98.0	 0.0	 94.0	 -94.0	 1.0	 100.0	 1	 188	 8.0; % NG
	2	 95.0	 0.0	 91.0	 -91.0	 1.0	 100.0	 1	 182	 8.0; % PEL
	2	 91.8	 0.0	 88.0	 -88.0	 1.0	 100.0	 1	 176	 7.6; % NG
	2	 335.3	 0.0	 332.0	 -332.0	 1.0	 100.0	 1	 663	 7.6; % COW
	7	 221.25	 0.0	 215.0	 -215.0	 1.0	 100.0	 1	 430	 12.5; % NG
	7	 82.75	 0.0	 77.0	 -77.0	 1.0	 100.0	 1	 153	 12.5; % NG
	7	 303.75	 0.0	 298.0	 -298.0	 1.0	 100.0	 1	 595	 12.5; % COW
	13	 289.25	 0.0	 272.0	 -272.0	 1.0	 100.0	 1	 544	 34.5; % NG
	13	 288.25	 0.0	 271.0	 -271.0	 1.0	 100.0	 1	 542	 34.5; % NG
	13	 321.75	 0.0	 305.0	 -305.0	 1.0	 100.0	 1	 609	 34.5; % COW
	14	 0.0	 35.8	 200.0	 -128.4	 1.0	 100.0	 1	 0	 0.0; % SYNC
	15	 80.1	 0.0	 80.0	 -80.0	 1.0	 100.0	 1	 159	 1.2; % NG
	15	 103.6	 0.0	 103.0	 -103.0	 1.0	 100.0	 1	 206	 1.2; % COW
	15	 98.1	 0.0	 98.0	 -98.0	 1.0	 100.0	 1	 195	 1.2; % NG
	15	 81.6	 0.0	 81.0	 -81.0	 1.0	 100.0	 1	 162	 1.2; % NG
	15	 103.6	 0.0	 103.0	 -103.0	 1.0	 100.0	 1	 206	 1.2; % NG
	15	 169.075	 0.0	 156.0	 -156.0	 1.0	 100.0	 1	 311	 27.15; % NG
	16	 717.075	 0.0	 704.0	 -704.0	 1.0	 100.0	 1	 1407	 27.15; % NG
	18	 98.0	 52.0	 200.0	 -96.0	 1.0	 100.0	 1	 146	 50.0; % NG
	21	 141.5	 41.5	 200.0	 -117.0	 1.0	 100.0	 1	 233	 50.0; % COW
	22	 26.0	 0.0	 24.0	 -24.0	 1.0	 100.0	 1	 47	 5.0; % NG
	22	 27.0	 0.0	 25.0	 -25.0	 1.0	 100.0	 1	 49	 5.0; % NG
	22	 25.5	 0.0	 23.0	 -23.0	 1.0	 100.0	 1	 46	 5.0; % NG
	22	 28.5	 0.0	 26.0	 -26.0	 1.0	 100.0	 1	 52	 5.0; % COW
	22	 15.5	 1.5	 16.0	 -13.0	 1.0	 100.0	 1	 26	 5.0; % NG
	22	 8.0	 3.0	 16.0	 -10.0	 1.0	 100.0	 1	 11	 5.0; % NG
	23	 292.575	 0.0	 279.0	 -279.0	 1.0	 100.0	 1	 558	 27.15; % NG
	23	 129.575	 0.0	 116.0	 -116.0	 1.0	 100.0	 1	 232	 27.15; % COW
	23	 281.0	 0.0	 246.0	 -246.0	 1.0	 100.0	 1	 492	 70.0; % NG
];

%% generator cost data
%	2	startup	shutdown	n	c(n-1)	...	c0
mpc.gencost = [
	2	 1500.0	 0.0	 3	   0.000000	 130.000000	 400.684900; % PEL
	2	 1500.0	 0.0	 3	   0.000000	 130.000000	 400.684900; % PEL
	2	 1500.0	 0.0	 3	   0.014142	  16.081100	 212.307600; % PEL
	2	 1500.0	 0.0	 3	   0.014142	  16.081100	 212.307600; % NG
	2	 1500.0	 0.0	 3	   0.000000	 130.000000	 400.684900; % NG
	2	 1500.0	 0.0	 3	   0.000000	 130.000000	 400.684900; % PEL
	2	 1500.0	 0.0	 3	   0.014142	  16.081100	 212.307600; % NG
	2	 1500.0	 0.0	 3	   0.014142	  16.081100	 212.307600; % COW
	2	 1500.0	 0.0	 3	   0.052672	  43.661500	 781.521000; % NG
	2	 1500.0	 0.0	 3	   0.052672	  43.661500	 781.521000; % NG
	2	 1500.0	 0.0	 3	   0.052672	  43.661500	 781.521000; % COW
	2	 1500.0	 0.0	 3	   0.007170	  48.580400	 832.757500; % NG
	2	 1500.0	 0.0	 3	   0.007170	  48.580400	 832.757500; % NG
	2	 1500.0	 0.0	 3	   0.007170	  48.580400	 832.757500; % COW
	2	 1500.0	 0.0	 3	   0.000000	   0.000000	   0.000000; % SYNC
	2	 1500.0	 0.0	 3	   0.328412	  56.564000	  86.385200; % NG
	2	 1500.0	 0.0	 3	   0.328412	  56.564000	  86.385200; % COW
	2	 1500.0	 0.0	 3	   0.328412	  56.564000	  86.385200; % NG
	2	 1500.0	 0.0	 3	   0.328412	  56.564000	  86.385200; % NG
	2	 1500.0	 0.0	 3	   0.328412	  56.564000	  86.385200; % NG
	2	 1500.0	 0.0	 3	   0.008342	  12.388300	 382.239100; % NG
	2	 1500.0	 0.0	 3	   0.008342	  12.388300	 382.239100; % NG
	2	 1500.0	 0.0	 3	   0.000213	   4.423100	 395.374900; % NG
	2	 1500.0	 0.0	 3	   0.000213	   4.423100	 395.374900; % COW
	2	 1500.0	 0.0	 3	   0.000000	   0.001000	   0.001000; % NG
	2	 1500.0	 0.0	 3	   0.000000	   0.001000	   0.001000; % NG
	2	 1500.0	 0.0	 3	   0.000000	   0.001000	   0.001000; % NG
	2	 1500.0	 0.0	 3	   0.000000	   0.001000	   0.001000; % COW
	2	 1500.0	 0.0	 3	   0.000000	   0.001000	   0.001000; % NG
	2	 1500.0	 0.0	 3	   0.000000	   0.001000	   0.001000; % NG
	2	 1500.0	 0.0	 3	   0.008342	  12.388300	 382.239100; % NG
	2	 1500.0	 0.0	 3	   0.008342	  12.388300	 382.239100; % COW
	2	 1500.0	 0.0	 3	   0.004895	  11.849500	 665.109400; % NG
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [
	1	 2	 0.0026	 0.0139	 0.4611	 175.0	 193.0	 200.0	 0.0	 0.0	 1	 -30.0	 30.0;
	1	 3	 0.0546	 0.2112	 0.0572	 175.0	 208.0	 220.0	 0.0	 0.0	 1	 -30.0	 30.0;
	1	 5	 0.0218	 0.0845	 0.0229	 175.0	 208.0	 220.0	 0.0	 0.0	 1	 -30.0	 30.0;
	2	 4	 0.0328	 0.1267	 0.0343	 175.0	 208.0	 220.0	 0.0	 0.0	 1	 -30.0	 30.0;
	2	 6	 0.0497	 0.192	 0.052	 175.0	 208.0	 220.0	 0.0	 0.0	 1	 -30.0	 30.0;
	3	 9	 0.0308	 0.119	 0.0322	 175.0	 208.0	 220.0	 0.0	 0.0	 1	 -30.0	 30.0;
	3	 24	 0.0023	 0.0839	 0.0	 400.0	 510.0	 600.0	 1.03	 0.0	 1	 -30.0	 30.0;
	4	 9	 0.0268	 0.1037	 0.0281	 175.0	 208.0	 220.0	 0.0	 0.0	 1	 -30.0	 30.0;
	5	 10	 0.0228	 0.0883	 0.0239	 175.0	 208.0	 220.0	 0.0	 0.0	 1	 -30.0	 30.0;
	6	 10	 0.0139	 0.0605	 2.459	 175.0	 193.0	 200.0	 0.0	 0.0	 1	 -30.0	 30.0;
	7	 8	 0.0159	 0.0614	 0.0166	 175.0	 208.0	 220.0	 0.0	 0.0	 1	 -30.0	 30.0;
	8	 9	 0.0427	 0.1651	 0.0447	 175.0	 208.0	 220.0	 0.0	 0.0	 1	 -30.0	 30.0;
	8	 10	 0.0427	 0.1651	 0.0447	 175.0	 208.0	 220.0	 0.0	 0.0	 1	 -30.0	 30.0;
	9	 11	 0.0023	 0.0839	 0.0	 400.0	 510.0	 600.0	 1.03	 0.0	 1	 -30.0	 30.0;
	9	 12	 0.0023	 0.0839	 0.0	 400.0	 510.0	 600.0	 1.03	 0.0	 1	 -30.0	 30.0;
	10	 11	 0.0023	 0.0839	 0.0	 400.0	 510.0	 600.0	 1.02	 0.0	 1	 -30.0	 30.0;
	10	 12	 0.0023	 0.0839	 0.0	 400.0	 510.0	 600.0	 1.02	 0.0	 1	 -30.0	 30.0;
	11	 13	 0.0061	 0.0476	 0.0999	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	11	 14	 0.0054	 0.0418	 0.0879	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	12	 13	 0.0061	 0.0476	 0.0999	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	12	 23	 0.0124	 0.0966	 0.203	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	13	 23	 0.0111	 0.0865	 0.1818	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	14	 16	 0.005	 0.0389	 0.0818	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	15	 16	 0.0022	 0.0173	 0.0364	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	15	 21	 0.0063	 0.049	 0.103	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	15	 21	 0.0063	 0.049	 0.103	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	15	 24	 0.0067	 0.0519	 0.1091	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	16	 17	 0.0033	 0.0259	 0.0545	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	16	 19	 0.003	 0.0231	 0.0485	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	17	 18	 0.0018	 0.0144	 0.0303	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	17	 22	 0.0135	 0.1053	 0.2212	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	18	 21	 0.0033	 0.0259	 0.0545	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	18	 21	 0.0033	 0.0259	 0.0545	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	19	 20	 0.0051	 0.0396	 0.0833	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	19	 20	 0.0051	 0.0396	 0.0833	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	20	 23	 0.0028	 0.0216	 0.0455	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	20	 23	 0.0028	 0.0216	 0.0455	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
	21	 22	 0.0087	 0.0678	 0.1424	 500.0	 600.0	 625.0	 0.0	 0.0	 1	 -30.0	 30.0;
];

% INFO    : === Translation Options ===
% INFO    : Load Model:                  from file ./pglib_opf_case24_ieee_rts.m.api.sol
% INFO    : Gen Active Capacity Model:   stat
% INFO    : Gen Reactive Capacity Model: al50ag
% INFO    : Gen Active Cost Model:       stat
% INFO    : 
% INFO    : === Load Replacement Notes ===
% INFO    : Bus 1	: Pd=108.0, Qd=22.0 -> Pd=207.30, Qd=22.00
% INFO    : Bus 2	: Pd=97.0, Qd=20.0 -> Pd=186.19, Qd=20.00
% INFO    : Bus 3	: Pd=180.0, Qd=37.0 -> Pd=345.50, Qd=37.00
% INFO    : Bus 4	: Pd=74.0, Qd=15.0 -> Pd=142.04, Qd=15.00
% INFO    : Bus 5	: Pd=71.0, Qd=14.0 -> Pd=136.28, Qd=14.00
% INFO    : Bus 6	: Pd=136.0, Qd=28.0 -> Pd=261.05, Qd=28.00
% INFO    : Bus 7	: Pd=125.0, Qd=25.0 -> Pd=239.93, Qd=25.00
% INFO    : Bus 8	: Pd=171.0, Qd=35.0 -> Pd=328.23, Qd=35.00
% INFO    : Bus 9	: Pd=175.0, Qd=36.0 -> Pd=335.90, Qd=36.00
% INFO    : Bus 10	: Pd=195.0, Qd=40.0 -> Pd=374.29, Qd=40.00
% INFO    : Bus 13	: Pd=265.0, Qd=54.0 -> Pd=508.66, Qd=54.00
% INFO    : Bus 14	: Pd=194.0, Qd=39.0 -> Pd=372.37, Qd=39.00
% INFO    : Bus 15	: Pd=317.0, Qd=64.0 -> Pd=608.47, Qd=64.00
% INFO    : Bus 16	: Pd=100.0, Qd=20.0 -> Pd=191.95, Qd=20.00
% INFO    : Bus 18	: Pd=333.0, Qd=68.0 -> Pd=639.18, Qd=68.00
% INFO    : Bus 19	: Pd=181.0, Qd=37.0 -> Pd=347.42, Qd=37.00
% INFO    : Bus 20	: Pd=128.0, Qd=26.0 -> Pd=245.69, Qd=26.00
% INFO    : 
% INFO    : === Generator Setpoint Replacement Notes ===
% INFO    : Gen at bus 1	: Pg=18.0, Qg=5.0 -> Pg=73.0, Qg=3.0
% INFO    : Gen at bus 1	: Pg=18.0, Qg=5.0 -> Pg=73.0, Qg=3.0
% INFO    : Gen at bus 1	: Pg=45.6, Qg=2.5 -> Pg=72.0, Qg=1.0
% INFO    : Gen at bus 1	: Pg=45.6, Qg=2.5 -> Pg=72.0, Qg=1.0
% INFO    : Gen at bus 2	: Pg=18.0, Qg=5.0 -> Pg=157.0, Qg=32.0
% INFO    : Gen at bus 2	: Pg=18.0, Qg=5.0 -> Pg=157.0, Qg=32.0
% INFO    : Gen at bus 2	: Pg=45.6, Qg=2.5 -> Pg=156.0, Qg=29.0
% INFO    : Gen at bus 2	: Pg=45.6, Qg=2.5 -> Pg=156.0, Qg=29.0
% INFO    : Gen at bus 7	: Pg=62.5, Qg=30.0 -> Pg=128.0, Qg=43.0
% INFO    : Gen at bus 7	: Pg=62.5, Qg=30.0 -> Pg=128.0, Qg=43.0
% INFO    : Gen at bus 7	: Pg=62.5, Qg=30.0 -> Pg=128.0, Qg=43.0
% INFO    : Gen at bus 13	: Pg=133.0, Qg=40.0 -> Pg=445.0, Qg=82.0
% INFO    : Gen at bus 13	: Pg=133.0, Qg=40.0 -> Pg=445.0, Qg=82.0
% INFO    : Gen at bus 13	: Pg=133.0, Qg=40.0 -> Pg=445.0, Qg=82.0
% INFO    : Gen at bus 14	: Pg=0.0, Qg=75.0 -> Pg=0.0, Qg=107.0
% INFO    : Gen at bus 15	: Pg=7.2, Qg=3.0 -> Pg=155.0, Qg=19.0
% INFO    : Gen at bus 15	: Pg=7.2, Qg=3.0 -> Pg=155.0, Qg=19.0
% INFO    : Gen at bus 15	: Pg=7.2, Qg=3.0 -> Pg=155.0, Qg=19.0
% INFO    : Gen at bus 15	: Pg=7.2, Qg=3.0 -> Pg=155.0, Qg=19.0
% INFO    : Gen at bus 15	: Pg=7.2, Qg=3.0 -> Pg=155.0, Qg=19.0
% INFO    : Gen at bus 15	: Pg=104.65, Qg=15.0 -> Pg=207.0, Qg=31.0
% INFO    : Gen at bus 16	: Pg=104.65, Qg=15.0 -> Pg=1246.0, Qg=32.0
% INFO    : Gen at bus 18	: Pg=250.0, Qg=75.0 -> Pg=102.0, Qg=80.0
% INFO    : Gen at bus 21	: Pg=250.0, Qg=75.0 -> Pg=101.0, Qg=77.0
% INFO    : Gen at bus 22	: Pg=30.0, Qg=3.0 -> Pg=11.0, Qg=-4.0
% INFO    : Gen at bus 22	: Pg=30.0, Qg=3.0 -> Pg=11.0, Qg=-4.0
% INFO    : Gen at bus 22	: Pg=30.0, Qg=3.0 -> Pg=11.0, Qg=-4.0
% INFO    : Gen at bus 22	: Pg=30.0, Qg=3.0 -> Pg=11.0, Qg=-4.0
% INFO    : Gen at bus 22	: Pg=30.0, Qg=3.0 -> Pg=11.0, Qg=-4.0
% INFO    : Gen at bus 22	: Pg=30.0, Qg=3.0 -> Pg=11.0, Qg=-4.0
% INFO    : Gen at bus 23	: Pg=104.65, Qg=15.0 -> Pg=125.0, Qg=30.0
% INFO    : Gen at bus 23	: Pg=104.65, Qg=15.0 -> Pg=125.0, Qg=30.0
% INFO    : Gen at bus 23	: Pg=245.0, Qg=62.5 -> Pg=210.0, Qg=77.0
% INFO    : 
% INFO    : === Generator Reactive Capacity Atleast Setpoint Value Notes ===
% INFO    : Gen at bus 1	: Qg 3.0, Qmin 0.0, Qmax 10.0 -> Qmin -3.6, Qmax 10.0
% INFO    : Gen at bus 1	: Qg 3.0, Qmin 0.0, Qmax 10.0 -> Qmin -3.6, Qmax 10.0
% INFO    : Gen at bus 2	: Qg 32.0, Qmin 0.0, Qmax 10.0 -> Qmin -38.4, Qmax 38.4
% INFO    : Gen at bus 2	: Qg 32.0, Qmin 0.0, Qmax 10.0 -> Qmin -38.4, Qmax 38.4
% INFO    : Gen at bus 2	: Qg 29.0, Qmin -25.0, Qmax 30.0 -> Qmin -34.8, Qmax 30.0
% INFO    : Gen at bus 2	: Qg 29.0, Qmin -25.0, Qmax 30.0 -> Qmin -34.8, Qmax 30.0
% INFO    : Gen at bus 7	: Qg 43.0, Qmin 0.0, Qmax 60.0 -> Qmin -51.6, Qmax 60.0
% INFO    : Gen at bus 7	: Qg 43.0, Qmin 0.0, Qmax 60.0 -> Qmin -51.6, Qmax 60.0
% INFO    : Gen at bus 7	: Qg 43.0, Qmin 0.0, Qmax 60.0 -> Qmin -51.6, Qmax 60.0
% INFO    : Gen at bus 13	: Qg 82.0, Qmin 0.0, Qmax 80.0 -> Qmin -98.4, Qmax 98.4
% INFO    : Gen at bus 13	: Qg 82.0, Qmin 0.0, Qmax 80.0 -> Qmin -98.4, Qmax 98.4
% INFO    : Gen at bus 13	: Qg 82.0, Qmin 0.0, Qmax 80.0 -> Qmin -98.4, Qmax 98.4
% INFO    : Gen at bus 14	: Qg 107.0, Qmin -50.0, Qmax 200.0 -> Qmin -128.4, Qmax 200.0
% INFO    : Gen at bus 15	: Qg 19.0, Qmin 0.0, Qmax 6.0 -> Qmin -22.8, Qmax 22.8
% INFO    : Gen at bus 15	: Qg 19.0, Qmin 0.0, Qmax 6.0 -> Qmin -22.8, Qmax 22.8
% INFO    : Gen at bus 15	: Qg 19.0, Qmin 0.0, Qmax 6.0 -> Qmin -22.8, Qmax 22.8
% INFO    : Gen at bus 15	: Qg 19.0, Qmin 0.0, Qmax 6.0 -> Qmin -22.8, Qmax 22.8
% INFO    : Gen at bus 15	: Qg 19.0, Qmin 0.0, Qmax 6.0 -> Qmin -22.8, Qmax 22.8
% INFO    : Gen at bus 18	: Qg 80.0, Qmin -50.0, Qmax 200.0 -> Qmin -96.0, Qmax 200.0
% INFO    : Gen at bus 21	: Qg 77.0, Qmin -50.0, Qmax 200.0 -> Qmin -92.4, Qmax 200.0
% INFO    : Gen at bus 23	: Qg 77.0, Qmin -25.0, Qmax 150.0 -> Qmin -92.4, Qmax 150.0
% INFO    : 
% INFO    : === Generator Classification Notes ===
% INFO    : PEL    4   -     6.71
% INFO    : SYNC   1   -     0.00
% INFO    : COW    7   -    20.05
% INFO    : NG     21  -    73.25
% INFO    : 
% INFO    : === Generator Active Capacity Stat Model Notes ===
% INFO    : Gen at bus 1 - PEL	: Pg=73.0, Pmax=20.0 -> Pmax=79   samples: 7
% INFO    : Gen at bus 1 - PEL	: Pg=73.0, Pmax=20.0 -> Pmax=211   samples: 1
% INFO    : Gen at bus 1 - PEL	: Pg=72.0, Pmax=76.0 -> Pmax=75   samples: 9
% INFO    : Gen at bus 1 - NG	: Pg=72.0, Pmax=76.0 -> Pmax=78   samples: 2
% INFO    : Gen at bus 2 - NG	: Pg=157.0, Pmax=20.0 -> Pmax=188   samples: 1
% WARNING : Failed to find a generator capacity within (157.0-785.0) after 100 samples, using percent increase model
% INFO    : Gen at bus 2 - PEL	: Pg=157.0, Pmax=20.0 -> Pmax=182   samples: 100
% INFO    : Gen at bus 2 - NG	: Pg=156.0, Pmax=76.0 -> Pmax=176   samples: 1
% INFO    : Gen at bus 2 - COW	: Pg=156.0, Pmax=76.0 -> Pmax=663   samples: 3
% INFO    : Gen at bus 7 - NG	: Pg=128.0, Pmax=100.0 -> Pmax=430   samples: 2
% INFO    : Gen at bus 7 - NG	: Pg=128.0, Pmax=100.0 -> Pmax=153   samples: 1
% INFO    : Gen at bus 7 - COW	: Pg=128.0, Pmax=100.0 -> Pmax=595   samples: 1
% INFO    : Gen at bus 13 - NG	: Pg=445.0, Pmax=197.0 -> Pmax=544   samples: 18
% INFO    : Gen at bus 13 - NG	: Pg=445.0, Pmax=197.0 -> Pmax=542   samples: 17
% INFO    : Gen at bus 13 - COW	: Pg=445.0, Pmax=197.0 -> Pmax=609   samples: 2
% INFO    : Gen at bus 14 - SYNC	: Pg=0.0, Pmax=0.0 -> Pmax=0   samples: 0
% INFO    : Gen at bus 15 - NG	: Pg=155.0, Pmax=12.0 -> Pmax=159   samples: 4
% INFO    : Gen at bus 15 - COW	: Pg=155.0, Pmax=12.0 -> Pmax=206   samples: 2
% INFO    : Gen at bus 15 - NG	: Pg=155.0, Pmax=12.0 -> Pmax=195   samples: 3
% INFO    : Gen at bus 15 - NG	: Pg=155.0, Pmax=12.0 -> Pmax=162   samples: 10
% INFO    : Gen at bus 15 - NG	: Pg=155.0, Pmax=12.0 -> Pmax=206   samples: 2
% INFO    : Gen at bus 15 - NG	: Pg=207.0, Pmax=155.0 -> Pmax=311   samples: 16
% WARNING : Failed to find a generator capacity within (1246.0-6230.0) after 100 samples, using percent increase model
% INFO    : Gen at bus 16 - NG	: Pg=1246.0, Pmax=155.0 -> Pmax=1407   samples: 100
% INFO    : Gen at bus 18 - NG	: Pg=102.0, Pmax=400.0 -> Pmax=146   samples: 1
% INFO    : Gen at bus 21 - COW	: Pg=101.0, Pmax=400.0 -> Pmax=233   samples: 1
% INFO    : Gen at bus 22 - NG	: Pg=11.0, Pmax=50.0 -> Pmax=47   samples: 9
% INFO    : Gen at bus 22 - NG	: Pg=11.0, Pmax=50.0 -> Pmax=49   samples: 4
% INFO    : Gen at bus 22 - NG	: Pg=11.0, Pmax=50.0 -> Pmax=46   samples: 6
% INFO    : Gen at bus 22 - COW	: Pg=11.0, Pmax=50.0 -> Pmax=52   samples: 12
% INFO    : Gen at bus 22 - NG	: Pg=11.0, Pmax=50.0 -> Pmax=26   samples: 13
% INFO    : Gen at bus 22 - NG	: Pg=11.0, Pmax=50.0 -> Pmax=11   samples: 3
% INFO    : Gen at bus 23 - NG	: Pg=125.0, Pmax=155.0 -> Pmax=558   samples: 1
% INFO    : Gen at bus 23 - COW	: Pg=125.0, Pmax=155.0 -> Pmax=232   samples: 5
% INFO    : Gen at bus 23 - NG	: Pg=210.0, Pmax=350.0 -> Pmax=492   samples: 6
% INFO    : 
% INFO    : === Generator Active Capacity LB Model Notes ===
% INFO    : Gen at bus 1	: Pmin=16.0 -> Pmin=8.0 
% INFO    : Gen at bus 1	: Pmin=16.0 -> Pmin=8.0 
% INFO    : Gen at bus 1	: Pmin=15.2 -> Pmin=7.6 
% INFO    : Gen at bus 1	: Pmin=15.2 -> Pmin=7.6 
% INFO    : Gen at bus 2	: Pmin=16.0 -> Pmin=8.0 
% INFO    : Gen at bus 2	: Pmin=16.0 -> Pmin=8.0 
% INFO    : Gen at bus 2	: Pmin=15.2 -> Pmin=7.6 
% INFO    : Gen at bus 2	: Pmin=15.2 -> Pmin=7.6 
% INFO    : Gen at bus 7	: Pmin=25.0 -> Pmin=12.5 
% INFO    : Gen at bus 7	: Pmin=25.0 -> Pmin=12.5 
% INFO    : Gen at bus 7	: Pmin=25.0 -> Pmin=12.5 
% INFO    : Gen at bus 13	: Pmin=69.0 -> Pmin=34.5 
% INFO    : Gen at bus 13	: Pmin=69.0 -> Pmin=34.5 
% INFO    : Gen at bus 13	: Pmin=69.0 -> Pmin=34.5 
% INFO    : Gen at bus 15	: Pmin=2.4 -> Pmin=1.2 
% INFO    : Gen at bus 15	: Pmin=2.4 -> Pmin=1.2 
% INFO    : Gen at bus 15	: Pmin=2.4 -> Pmin=1.2 
% INFO    : Gen at bus 15	: Pmin=2.4 -> Pmin=1.2 
% INFO    : Gen at bus 15	: Pmin=2.4 -> Pmin=1.2 
% INFO    : Gen at bus 15	: Pmin=54.3 -> Pmin=27.15 
% INFO    : Gen at bus 16	: Pmin=54.3 -> Pmin=27.15 
% INFO    : Gen at bus 18	: Pmin=100.0 -> Pmin=50.0 
% INFO    : Gen at bus 21	: Pmin=100.0 -> Pmin=50.0 
% INFO    : Gen at bus 22	: Pmin=10.0 -> Pmin=5.0 
% INFO    : Gen at bus 22	: Pmin=10.0 -> Pmin=5.0 
% INFO    : Gen at bus 22	: Pmin=10.0 -> Pmin=5.0 
% INFO    : Gen at bus 22	: Pmin=10.0 -> Pmin=5.0 
% INFO    : Gen at bus 22	: Pmin=10.0 -> Pmin=5.0 
% INFO    : Gen at bus 22	: Pmin=10.0 -> Pmin=5.0 
% INFO    : Gen at bus 23	: Pmin=54.3 -> Pmin=27.15 
% INFO    : Gen at bus 23	: Pmin=54.3 -> Pmin=27.15 
% INFO    : Gen at bus 23	: Pmin=140.0 -> Pmin=70.0 
% INFO    : 
% INFO    : === Generator Reactive Capacity Atleast Max 50 Percent Active Model Notes ===
% INFO    : Gen at bus 1 - PEL	: Pmax 79.0, Qmin -3.6, Qmax 10.0 -> Qmin -40.0, Qmax 40.0
% INFO    : Gen at bus 1 - PEL	: Pmax 211.0, Qmin -3.6, Qmax 10.0 -> Qmin -106.0, Qmax 106.0
% INFO    : Gen at bus 1 - PEL	: Pmax 75.0, Qmin -25.0, Qmax 30.0 -> Qmin -38.0, Qmax 38.0
% INFO    : Gen at bus 1 - NG	: Pmax 78.0, Qmin -25.0, Qmax 30.0 -> Qmin -39.0, Qmax 39.0
% INFO    : Gen at bus 2 - NG	: Pmax 188.0, Qmin -38.4, Qmax 38.4 -> Qmin -94.0, Qmax 94.0
% INFO    : Gen at bus 2 - PEL	: Pmax 182.0, Qmin -38.4, Qmax 38.4 -> Qmin -91.0, Qmax 91.0
% INFO    : Gen at bus 2 - NG	: Pmax 176.0, Qmin -34.8, Qmax 30.0 -> Qmin -88.0, Qmax 88.0
% INFO    : Gen at bus 2 - COW	: Pmax 663.0, Qmin -34.8, Qmax 30.0 -> Qmin -332.0, Qmax 332.0
% INFO    : Gen at bus 7 - NG	: Pmax 430.0, Qmin -51.6, Qmax 60.0 -> Qmin -215.0, Qmax 215.0
% INFO    : Gen at bus 7 - NG	: Pmax 153.0, Qmin -51.6, Qmax 60.0 -> Qmin -77.0, Qmax 77.0
% INFO    : Gen at bus 7 - COW	: Pmax 595.0, Qmin -51.6, Qmax 60.0 -> Qmin -298.0, Qmax 298.0
% INFO    : Gen at bus 13 - NG	: Pmax 544.0, Qmin -98.4, Qmax 98.4 -> Qmin -272.0, Qmax 272.0
% INFO    : Gen at bus 13 - NG	: Pmax 542.0, Qmin -98.4, Qmax 98.4 -> Qmin -271.0, Qmax 271.0
% INFO    : Gen at bus 13 - COW	: Pmax 609.0, Qmin -98.4, Qmax 98.4 -> Qmin -305.0, Qmax 305.0
% INFO    : Gen at bus 15 - NG	: Pmax 159.0, Qmin -22.8, Qmax 22.8 -> Qmin -80.0, Qmax 80.0
% INFO    : Gen at bus 15 - COW	: Pmax 206.0, Qmin -22.8, Qmax 22.8 -> Qmin -103.0, Qmax 103.0
% INFO    : Gen at bus 15 - NG	: Pmax 195.0, Qmin -22.8, Qmax 22.8 -> Qmin -98.0, Qmax 98.0
% INFO    : Gen at bus 15 - NG	: Pmax 162.0, Qmin -22.8, Qmax 22.8 -> Qmin -81.0, Qmax 81.0
% INFO    : Gen at bus 15 - NG	: Pmax 206.0, Qmin -22.8, Qmax 22.8 -> Qmin -103.0, Qmax 103.0
% INFO    : Gen at bus 15 - NG	: Pmax 311.0, Qmin -50.0, Qmax 80.0 -> Qmin -156.0, Qmax 156.0
% INFO    : Gen at bus 16 - NG	: Pmax 1407.0, Qmin -50.0, Qmax 80.0 -> Qmin -704.0, Qmax 704.0
% INFO    : Gen at bus 21 - COW	: Pmax 233.0, Qmin -92.4, Qmax 200.0 -> Qmin -117.0, Qmax 200.0
% INFO    : Gen at bus 22 - NG	: Pmax 47.0, Qmin -10.0, Qmax 16.0 -> Qmin -24.0, Qmax 24.0
% INFO    : Gen at bus 22 - NG	: Pmax 49.0, Qmin -10.0, Qmax 16.0 -> Qmin -25.0, Qmax 25.0
% INFO    : Gen at bus 22 - NG	: Pmax 46.0, Qmin -10.0, Qmax 16.0 -> Qmin -23.0, Qmax 23.0
% INFO    : Gen at bus 22 - COW	: Pmax 52.0, Qmin -10.0, Qmax 16.0 -> Qmin -26.0, Qmax 26.0
% INFO    : Gen at bus 22 - NG	: Pmax 26.0, Qmin -10.0, Qmax 16.0 -> Qmin -13.0, Qmax 16.0
% INFO    : Gen at bus 23 - NG	: Pmax 558.0, Qmin -50.0, Qmax 80.0 -> Qmin -279.0, Qmax 279.0
% INFO    : Gen at bus 23 - COW	: Pmax 232.0, Qmin -50.0, Qmax 80.0 -> Qmin -116.0, Qmax 116.0
% INFO    : Gen at bus 23 - NG	: Pmax 492.0, Qmin -92.4, Qmax 150.0 -> Qmin -246.0, Qmax 246.0
% INFO    : 
% INFO    : === Generator Setpoint Replacement Notes ===
% INFO    : Gen at bus 1	: Pg=73.0, Qg=3.0 -> Pg=43.5, Qg=0.0
% INFO    : Gen at bus 1	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 1	: Pg=73.0, Qg=3.0 -> Pg=109.5, Qg=0.0
% INFO    : Gen at bus 1	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 1	: Pg=72.0, Qg=1.0 -> Pg=41.3, Qg=0.0
% INFO    : Gen at bus 1	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 1	: Pg=72.0, Qg=1.0 -> Pg=42.8, Qg=0.0
% INFO    : Gen at bus 1	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 2	: Pg=157.0, Qg=32.0 -> Pg=98.0, Qg=0.0
% INFO    : Gen at bus 2	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 2	: Pg=157.0, Qg=32.0 -> Pg=95.0, Qg=0.0
% INFO    : Gen at bus 2	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 2	: Pg=156.0, Qg=29.0 -> Pg=91.8, Qg=0.0
% INFO    : Gen at bus 2	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 2	: Pg=156.0, Qg=29.0 -> Pg=335.3, Qg=0.0
% INFO    : Gen at bus 2	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 7	: Pg=128.0, Qg=43.0 -> Pg=221.25, Qg=0.0
% INFO    : Gen at bus 7	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 7	: Pg=128.0, Qg=43.0 -> Pg=82.75, Qg=0.0
% INFO    : Gen at bus 7	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 7	: Pg=128.0, Qg=43.0 -> Pg=303.75, Qg=0.0
% INFO    : Gen at bus 7	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 13	: Pg=445.0, Qg=82.0 -> Pg=289.25, Qg=0.0
% INFO    : Gen at bus 13	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 13	: Pg=445.0, Qg=82.0 -> Pg=288.25, Qg=0.0
% INFO    : Gen at bus 13	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 13	: Pg=445.0, Qg=82.0 -> Pg=321.75, Qg=0.0
% INFO    : Gen at bus 13	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 14	: Pg=0.0, Qg=107.0 -> Pg=0.0, Qg=35.8
% INFO    : Gen at bus 14	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 15	: Pg=155.0, Qg=19.0 -> Pg=80.1, Qg=0.0
% INFO    : Gen at bus 15	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 15	: Pg=155.0, Qg=19.0 -> Pg=103.6, Qg=0.0
% INFO    : Gen at bus 15	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 15	: Pg=155.0, Qg=19.0 -> Pg=98.1, Qg=0.0
% INFO    : Gen at bus 15	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 15	: Pg=155.0, Qg=19.0 -> Pg=81.6, Qg=0.0
% INFO    : Gen at bus 15	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 15	: Pg=155.0, Qg=19.0 -> Pg=103.6, Qg=0.0
% INFO    : Gen at bus 15	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 15	: Pg=207.0, Qg=31.0 -> Pg=169.075, Qg=0.0
% INFO    : Gen at bus 15	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 16	: Pg=1246.0, Qg=32.0 -> Pg=717.075, Qg=0.0
% INFO    : Gen at bus 16	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 18	: Pg=102.0, Qg=80.0 -> Pg=98.0, Qg=52.0
% INFO    : Gen at bus 18	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 21	: Pg=101.0, Qg=77.0 -> Pg=141.5, Qg=41.5
% INFO    : Gen at bus 21	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 22	: Pg=11.0, Qg=-4.0 -> Pg=26.0, Qg=0.0
% INFO    : Gen at bus 22	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 22	: Pg=11.0, Qg=-4.0 -> Pg=27.0, Qg=0.0
% INFO    : Gen at bus 22	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 22	: Pg=11.0, Qg=-4.0 -> Pg=25.5, Qg=0.0
% INFO    : Gen at bus 22	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 22	: Pg=11.0, Qg=-4.0 -> Pg=28.5, Qg=0.0
% INFO    : Gen at bus 22	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 22	: Pg=11.0, Qg=-4.0 -> Pg=15.5, Qg=1.5
% INFO    : Gen at bus 22	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 22	: Pg=11.0, Qg=-4.0 -> Pg=8.0, Qg=3.0
% INFO    : Gen at bus 22	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 23	: Pg=125.0, Qg=30.0 -> Pg=292.575, Qg=0.0
% INFO    : Gen at bus 23	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 23	: Pg=125.0, Qg=30.0 -> Pg=129.575, Qg=0.0
% INFO    : Gen at bus 23	: Vg=1.0 -> Vg=1.0
% INFO    : Gen at bus 23	: Pg=210.0, Qg=77.0 -> Pg=281.0, Qg=0.0
% INFO    : Gen at bus 23	: Vg=1.0 -> Vg=1.0
% INFO    : 
% INFO    : === Writing Matpower Case File Notes ===
