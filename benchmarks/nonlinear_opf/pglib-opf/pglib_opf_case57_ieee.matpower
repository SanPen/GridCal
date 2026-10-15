%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%                                                                  %%%%%
%%%%    IEEE PES Power Grid Library - Optimal Power Flow - v23.07     %%%%%
%%%%          (https://github.com/power-grid-lib/pglib-opf)           %%%%%
%%%%               Benchmark Group - Typical Operations               %%%%%
%%%%                         23 - July - 2023                         %%%%%
%%%%                                                                  %%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%
%   Power flow data for IEEE 57 bus test case.
%   This data was converted from IEEE Common Data Format
%   (ieee57cdf.txt) on 20-Sep-2004 by cdf2matp, rev. 1.11
%
%   Converted from IEEE CDF file from:
%       http://www.ee.washington.edu/research/pstca/
%
%   Manually modified Qmax, Qmin on generator 1 to 200, -140, respectively.
%
%   Copyright (c) 1999 by Richard D. Christie, University of Washington
%   Electrical Engineering Licensed under the Creative Commons Attribution 4.0
%   International license, http://creativecommons.org/licenses/by/4.0/
%
%   CDF Header:
%   08/25/93 UW ARCHIVE           100.0  1961 W IEEE 57 Bus Test Case
%   
function mpc = pglib_opf_case57_ieee
mpc.version = '2';
mpc.baseMVA = 100.0;

%% bus data
%	bus_i	type	Pd	Qd	Gs	Bs	area	Vm	Va	baseKV	zone	Vmax	Vmin
mpc.bus = [
	1	 3	 55.0	 17.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	2	 2	 3.0	 88.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	3	 2	 41.0	 21.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	4	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	5	 1	 13.0	 4.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	6	 2	 75.0	 2.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	7	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	8	 2	 150.0	 22.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	9	 2	 121.0	 26.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	10	 1	 5.0	 2.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	11	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	12	 2	 377.0	 24.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	13	 1	 18.0	 2.3	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	14	 1	 10.5	 5.3	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	15	 1	 22.0	 5.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	16	 1	 43.0	 3.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	17	 1	 42.0	 8.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	18	 1	 27.2	 9.8	 0.0	 10.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	19	 1	 3.3	 0.6	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	20	 1	 2.3	 1.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	21	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	22	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	23	 1	 6.3	 2.1	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	24	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	25	 1	 6.3	 3.2	 0.0	 5.9	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	26	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	27	 1	 9.3	 0.5	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	28	 1	 4.6	 2.3	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	29	 1	 17.0	 2.6	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	30	 1	 3.6	 1.8	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	31	 1	 5.8	 2.9	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	32	 1	 1.6	 0.8	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	33	 1	 3.8	 1.9	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	34	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	35	 1	 6.0	 3.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	36	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	37	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	38	 1	 14.0	 7.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	39	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	40	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	41	 1	 6.3	 3.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	42	 1	 7.1	 4.4	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	43	 1	 2.0	 1.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	44	 1	 12.0	 1.8	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	45	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	46	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	47	 1	 29.7	 11.6	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	48	 1	 0.0	 0.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	49	 1	 18.0	 8.5	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	50	 1	 21.0	 10.5	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	51	 1	 18.0	 5.3	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	52	 1	 4.9	 2.2	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	53	 1	 20.0	 10.0	 0.0	 6.3	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	54	 1	 4.1	 1.4	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	55	 1	 6.8	 3.4	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	56	 1	 7.6	 2.2	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
	57	 1	 6.7	 2.0	 0.0	 0.0	 1	    1.00000	    0.00000	 1.0	 1	    1.06000	    0.94000;
];

%% generator data
%	bus	Pg	Qg	Qmax	Qmin	Vg	mBase	status	Pmax	Pmin
mpc.gen = [
	1	 122.5	 0.0	 123.0	 -123.0	 1.0	 100.0	 1	 245	 0.0; % COW
	2	 0.0	 16.5	 50.0	 -17.0	 1.0	 100.0	 1	 0	 0.0; % SYNC
	3	 30.0	 10.0	 30.0	 -10.0	 1.0	 100.0	 1	 60	 0.0; % NG
	6	 0.0	 8.5	 25.0	 -8.0	 1.0	 100.0	 1	 0	 0.0; % SYNC
	8	 579.5	 30.0	 200.0	 -140.0	 1.0	 100.0	 1	 1159	 0.0; % COW
	9	 0.0	 3.0	 9.0	 -3.0	 1.0	 100.0	 1	 0	 0.0; % SYNC
	12	 259.5	 2.5	 155.0	 -150.0	 1.0	 100.0	 1	 519	 0.0; % NG
];

%% generator cost data
%	2	startup	shutdown	n	c(n-1)	...	c0
mpc.gencost = [
	2	 0.0	 0.0	 3	   0.000000	  16.960624	   0.000000; % COW
	2	 0.0	 0.0	 3	   0.000000	   0.000000	   0.000000; % SYNC
	2	 0.0	 0.0	 3	   0.000000	  34.075557	   0.000000; % NG
	2	 0.0	 0.0	 3	   0.000000	   0.000000	   0.000000; % SYNC
	2	 0.0	 0.0	 3	   0.000000	  30.441037	   0.000000; % COW
	2	 0.0	 0.0	 3	   0.000000	   0.000000	   0.000000; % SYNC
	2	 0.0	 0.0	 3	   0.000000	  37.188979	   0.000000; % NG
];

%% branch data
%	fbus	tbus	r	x	b	rateA	rateB	rateC	ratio	angle	status	angmin	angmax
mpc.branch = [
	1	 2	 0.0083	 0.028	 0.129	 1005	 1005	 1005	 0.0	 0.0	 1	 -30.0	 30.0;
	2	 3	 0.0298	 0.085	 0.0818	 326	 326	 326	 0.0	 0.0	 1	 -30.0	 30.0;
	3	 4	 0.0112	 0.0366	 0.038	 767	 767	 767	 0.0	 0.0	 1	 -30.0	 30.0;
	4	 5	 0.0625	 0.132	 0.0258	 201	 201	 201	 0.0	 0.0	 1	 -30.0	 30.0;
	4	 6	 0.043	 0.148	 0.0348	 191	 191	 191	 0.0	 0.0	 1	 -30.0	 30.0;
	6	 7	 0.02	 0.102	 0.0276	 283	 283	 283	 0.0	 0.0	 1	 -30.0	 30.0;
	6	 8	 0.0339	 0.173	 0.047	 167	 167	 167	 0.0	 0.0	 1	 -30.0	 30.0;
	8	 9	 0.0099	 0.0505	 0.0548	 570	 570	 570	 0.0	 0.0	 1	 -30.0	 30.0;
	9	 10	 0.0369	 0.1679	 0.044	 171	 171	 171	 0.0	 0.0	 1	 -30.0	 30.0;
	9	 11	 0.0258	 0.0848	 0.0218	 331	 331	 331	 0.0	 0.0	 1	 -30.0	 30.0;
	9	 12	 0.0648	 0.295	 0.0772	 98	 98	 98	 0.0	 0.0	 1	 -30.0	 30.0;
	9	 13	 0.0481	 0.158	 0.0406	 178	 178	 178	 0.0	 0.0	 1	 -30.0	 30.0;
	13	 14	 0.0132	 0.0434	 0.011	 647	 647	 647	 0.0	 0.0	 1	 -30.0	 30.0;
	13	 15	 0.0269	 0.0869	 0.023	 323	 323	 323	 0.0	 0.0	 1	 -30.0	 30.0;
	1	 15	 0.0178	 0.091	 0.0988	 317	 317	 317	 0.0	 0.0	 1	 -30.0	 30.0;
	1	 16	 0.0454	 0.206	 0.0546	 140	 140	 140	 0.0	 0.0	 1	 -30.0	 30.0;
	1	 17	 0.0238	 0.108	 0.0286	 266	 266	 266	 0.0	 0.0	 1	 -30.0	 30.0;
	3	 15	 0.0162	 0.053	 0.0544	 530	 530	 530	 0.0	 0.0	 1	 -30.0	 30.0;
	4	 18	 0.0	 0.555	 0.0	 53	 53	 53	 0.97	 0.0	 1	 -30.0	 30.0;
	4	 18	 0.0	 0.43	 0.0	 69	 69	 69	 0.978	 0.0	 1	 -30.0	 30.0;
	5	 6	 0.0302	 0.0641	 0.0124	 414	 414	 414	 0.0	 0.0	 1	 -30.0	 30.0;
	7	 8	 0.0139	 0.0712	 0.0194	 405	 405	 405	 0.0	 0.0	 1	 -30.0	 30.0;
	10	 12	 0.0277	 0.1262	 0.0328	 228	 228	 228	 0.0	 0.0	 1	 -30.0	 30.0;
	11	 13	 0.0223	 0.0732	 0.0188	 384	 384	 384	 0.0	 0.0	 1	 -30.0	 30.0;
	12	 13	 0.0178	 0.058	 0.0604	 484	 484	 484	 0.0	 0.0	 1	 -30.0	 30.0;
	12	 16	 0.018	 0.0813	 0.0216	 353	 353	 353	 0.0	 0.0	 1	 -30.0	 30.0;
	12	 17	 0.0397	 0.179	 0.0476	 160	 160	 160	 0.0	 0.0	 1	 -30.0	 30.0;
	14	 15	 0.0171	 0.0547	 0.0148	 512	 512	 512	 0.0	 0.0	 1	 -30.0	 30.0;
	18	 19	 0.461	 0.685	 0.0	 36	 36	 36	 0.0	 0.0	 1	 -30.0	 30.0;
	19	 20	 0.283	 0.434	 0.0	 57	 57	 57	 0.0	 0.0	 1	 -30.0	 30.0;
	21	 20	 0.0	 0.7767	 0.0	 38	 38	 38	 1.043	 0.0	 1	 -30.0	 30.0;
	21	 22	 0.0736	 0.117	 0.0	 213	 213	 213	 0.0	 0.0	 1	 -30.0	 30.0;
	22	 23	 0.0099	 0.0152	 0.0	 1617	 1617	 1617	 0.0	 0.0	 1	 -30.0	 30.0;
	23	 24	 0.166	 0.256	 0.0084	 97	 97	 97	 0.0	 0.0	 1	 -30.0	 30.0;
	24	 25	 0.0	 1.182	 0.0	 25	 25	 25	 1.0	 0.0	 1	 -30.0	 30.0;
	24	 25	 0.0	 1.23	 0.0	 24	 24	 24	 1.0	 0.0	 1	 -30.0	 30.0;
	24	 26	 0.0	 0.0473	 0.0	 621	 621	 621	 1.043	 0.0	 1	 -30.0	 30.0;
	26	 27	 0.165	 0.254	 0.0	 97	 97	 97	 0.0	 0.0	 1	 -30.0	 30.0;
	27	 28	 0.0618	 0.0954	 0.0	 259	 259	 259	 0.0	 0.0	 1	 -30.0	 30.0;
	28	 29	 0.0418	 0.0587	 0.0	 408	 408	 408	 0.0	 0.0	 1	 -30.0	 30.0;
	7	 29	 0.0	 0.0648	 0.0	 453	 453	 453	 0.967	 0.0	 1	 -30.0	 30.0;
	25	 30	 0.135	 0.202	 0.0	 121	 121	 121	 0.0	 0.0	 1	 -30.0	 30.0;
	30	 31	 0.326	 0.497	 0.0	 50	 50	 50	 0.0	 0.0	 1	 -30.0	 30.0;
	31	 32	 0.507	 0.755	 0.0	 33	 33	 33	 0.0	 0.0	 1	 -30.0	 30.0;
	32	 33	 0.0392	 0.036	 0.0	 552	 552	 552	 0.0	 0.0	 1	 -30.0	 30.0;
	34	 32	 0.0	 0.953	 0.0	 31	 31	 31	 0.975	 0.0	 1	 -30.0	 30.0;
	34	 35	 0.052	 0.078	 0.0032	 313	 313	 313	 0.0	 0.0	 1	 -30.0	 30.0;
	35	 36	 0.043	 0.0537	 0.0016	 427	 427	 427	 0.0	 0.0	 1	 -30.0	 30.0;
	36	 37	 0.029	 0.0366	 0.0	 629	 629	 629	 0.0	 0.0	 1	 -30.0	 30.0;
	37	 38	 0.0651	 0.1009	 0.002	 245	 245	 245	 0.0	 0.0	 1	 -30.0	 30.0;
	37	 39	 0.0239	 0.0379	 0.0	 655	 655	 655	 0.0	 0.0	 1	 -30.0	 30.0;
	36	 40	 0.03	 0.0466	 0.0	 530	 530	 530	 0.0	 0.0	 1	 -30.0	 30.0;
	22	 38	 0.0192	 0.0295	 0.0	 834	 834	 834	 0.0	 0.0	 1	 -30.0	 30.0;
	11	 41	 0.0	 0.749	 0.0	 40	 40	 40	 0.955	 0.0	 1	 -30.0	 30.0;
	41	 42	 0.207	 0.352	 0.0	 72	 72	 72	 0.0	 0.0	 1	 -30.0	 30.0;
	41	 43	 0.0	 0.412	 0.0	 72	 72	 72	 0.0	 0.0	 1	 -30.0	 30.0;
	38	 44	 0.0289	 0.0585	 0.002	 450	 450	 450	 0.0	 0.0	 1	 -30.0	 30.0;
	15	 45	 0.0	 0.1042	 0.0	 282	 282	 282	 0.955	 0.0	 1	 -30.0	 30.0;
	14	 46	 0.0	 0.0735	 0.0	 400	 400	 400	 0.9	 0.0	 1	 -30.0	 30.0;
	46	 47	 0.023	 0.068	 0.0032	 409	 409	 409	 0.0	 0.0	 1	 -30.0	 30.0;
	47	 48	 0.0182	 0.0233	 0.0	 993	 993	 993	 0.0	 0.0	 1	 -30.0	 30.0;
	48	 49	 0.0834	 0.129	 0.0048	 191	 191	 191	 0.0	 0.0	 1	 -30.0	 30.0;
	49	 50	 0.0801	 0.128	 0.0	 195	 195	 195	 0.0	 0.0	 1	 -30.0	 30.0;
	50	 51	 0.1386	 0.22	 0.0	 113	 113	 113	 0.0	 0.0	 1	 -30.0	 30.0;
	10	 51	 0.0	 0.0712	 0.0	 412	 412	 412	 0.93	 0.0	 1	 -30.0	 30.0;
	13	 49	 0.0	 0.191	 0.0	 154	 154	 154	 0.895	 0.0	 1	 -30.0	 30.0;
	29	 52	 0.1442	 0.187	 0.0	 125	 125	 125	 0.0	 0.0	 1	 -30.0	 30.0;
	52	 53	 0.0762	 0.0984	 0.0	 236	 236	 236	 0.0	 0.0	 1	 -30.0	 30.0;
	53	 54	 0.1878	 0.232	 0.0	 99	 99	 99	 0.0	 0.0	 1	 -30.0	 30.0;
	54	 55	 0.1732	 0.2265	 0.0	 103	 103	 103	 0.0	 0.0	 1	 -30.0	 30.0;
	11	 43	 0.0	 0.153	 0.0	 192	 192	 192	 0.958	 0.0	 1	 -30.0	 30.0;
	44	 45	 0.0624	 0.1242	 0.004	 212	 212	 212	 0.0	 0.0	 1	 -30.0	 30.0;
	40	 56	 0.0	 1.195	 0.0	 25	 25	 25	 0.958	 0.0	 1	 -30.0	 30.0;
	56	 41	 0.553	 0.549	 0.0	 38	 38	 38	 0.0	 0.0	 1	 -30.0	 30.0;
	56	 42	 0.2125	 0.354	 0.0	 72	 72	 72	 0.0	 0.0	 1	 -30.0	 30.0;
	39	 57	 0.0	 1.355	 0.0	 22	 22	 22	 0.98	 0.0	 1	 -30.0	 30.0;
	57	 56	 0.174	 0.26	 0.0	 94	 94	 94	 0.0	 0.0	 1	 -30.0	 30.0;
	38	 49	 0.115	 0.177	 0.003	 139	 139	 139	 0.0	 0.0	 1	 -30.0	 30.0;
	38	 48	 0.0312	 0.0482	 0.0	 511	 511	 511	 0.0	 0.0	 1	 -30.0	 30.0;
	9	 55	 0.0	 0.1205	 0.0	 244	 244	 244	 0.94	 0.0	 1	 -30.0	 30.0;
];

% INFO    : === Translation Options ===
% INFO    : Phase Angle Bound:           30.0 (deg.)
% INFO    : Line Capacity Model:         stat
% INFO    : Gen Active Capacity Model:   stat
% INFO    : Gen Reactive Capacity Model: am50ag
% INFO    : Gen Active Cost Model:       stat
% INFO    : Setting Flat Start
% INFO    : Line Capacity PAB:           15.0 (deg.)
% INFO    : 
% INFO    : === Generator Classification Notes ===
% INFO    : SYNC   3   -     0.00
% INFO    : COW    2   -    62.32
% INFO    : NG     2   -    37.68
% INFO    : 
% INFO    : === Generator Active Capacity Stat Model Notes ===
% INFO    : Gen at bus 1 - COW	: Pg=128.9, Pmax=575.88 -> Pmax=245   samples: 1
% INFO    : Gen at bus 2 - SYNC	: Pg=0.0, Pmax=100.0 -> Pmax=0   samples: 0
% INFO    : Gen at bus 3 - NG	: Pg=40.0, Pmax=140.0 -> Pmax=60   samples: 1
% INFO    : Gen at bus 6 - SYNC	: Pg=0.0, Pmax=100.0 -> Pmax=0   samples: 0
% INFO    : Gen at bus 8 - COW	: Pg=450.0, Pmax=550.0 -> Pmax=1159   samples: 4
% INFO    : Gen at bus 9 - SYNC	: Pg=0.0, Pmax=100.0 -> Pmax=0   samples: 0
% INFO    : Gen at bus 12 - NG	: Pg=310.0, Pmax=410.0 -> Pmax=519   samples: 3
% INFO    : 
% INFO    : === Generator Reactive Capacity Atmost Max 50 Percent Active Model Notes ===
% INFO    : Gen at bus 1 - COW	: Pmax 245.0, Qmin -140.0, Qmax 200.0 -> Qmin -123.0, Qmax 123.0
% INFO    : Gen at bus 3 - NG	: Pmax 60.0, Qmin -10.0, Qmax 60.0 -> Qmin -10.0, Qmax 30.0
% INFO    : 
% INFO    : === Generator Active Cost Stat Model Notes ===
% INFO    : Updated Generator Cost: COW - 0.0 20.0 0.0775795 -> 0 16.9606236621 0
% INFO    : Updated Generator Cost: SYNC - 0.0 40.0 0.01 -> 0 0.0 0
% INFO    : Updated Generator Cost: NG - 0.0 20.0 0.25 -> 0 34.0755570884 0
% INFO    : Updated Generator Cost: SYNC - 0.0 40.0 0.01 -> 0 0.0 0
% INFO    : Updated Generator Cost: COW - 0.0 20.0 0.0222222 -> 0 30.4410370704 0
% INFO    : Updated Generator Cost: SYNC - 0.0 40.0 0.01 -> 0 0.0 0
% INFO    : Updated Generator Cost: NG - 0.0 20.0 0.0322581 -> 0 37.1889785807 0
% INFO    : 
% INFO    : === Generator Bounds Update Notes ===
% INFO    : 
% INFO    : === Base KV Replacement Notes ===
% WARNING : Bus 1 : basekv changed 0.0 => 1.0
% WARNING : Bus 2 : basekv changed 0.0 => 1.0
% WARNING : Bus 3 : basekv changed 0.0 => 1.0
% WARNING : Bus 4 : basekv changed 0.0 => 1.0
% WARNING : Bus 5 : basekv changed 0.0 => 1.0
% WARNING : Bus 6 : basekv changed 0.0 => 1.0
% WARNING : Bus 7 : basekv changed 0.0 => 1.0
% WARNING : Bus 8 : basekv changed 0.0 => 1.0
% WARNING : Bus 9 : basekv changed 0.0 => 1.0
% WARNING : Bus 10 : basekv changed 0.0 => 1.0
% WARNING : Bus 11 : basekv changed 0.0 => 1.0
% WARNING : Bus 12 : basekv changed 0.0 => 1.0
% WARNING : Bus 13 : basekv changed 0.0 => 1.0
% WARNING : Bus 14 : basekv changed 0.0 => 1.0
% WARNING : Bus 15 : basekv changed 0.0 => 1.0
% WARNING : Bus 16 : basekv changed 0.0 => 1.0
% WARNING : Bus 17 : basekv changed 0.0 => 1.0
% WARNING : Bus 18 : basekv changed 0.0 => 1.0
% WARNING : Bus 19 : basekv changed 0.0 => 1.0
% WARNING : Bus 20 : basekv changed 0.0 => 1.0
% WARNING : Bus 21 : basekv changed 0.0 => 1.0
% WARNING : Bus 22 : basekv changed 0.0 => 1.0
% WARNING : Bus 23 : basekv changed 0.0 => 1.0
% WARNING : Bus 24 : basekv changed 0.0 => 1.0
% WARNING : Bus 25 : basekv changed 0.0 => 1.0
% WARNING : Bus 26 : basekv changed 0.0 => 1.0
% WARNING : Bus 27 : basekv changed 0.0 => 1.0
% WARNING : Bus 28 : basekv changed 0.0 => 1.0
% WARNING : Bus 29 : basekv changed 0.0 => 1.0
% WARNING : Bus 30 : basekv changed 0.0 => 1.0
% WARNING : Bus 31 : basekv changed 0.0 => 1.0
% WARNING : Bus 32 : basekv changed 0.0 => 1.0
% WARNING : Bus 33 : basekv changed 0.0 => 1.0
% WARNING : Bus 34 : basekv changed 0.0 => 1.0
% WARNING : Bus 35 : basekv changed 0.0 => 1.0
% WARNING : Bus 36 : basekv changed 0.0 => 1.0
% WARNING : Bus 37 : basekv changed 0.0 => 1.0
% WARNING : Bus 38 : basekv changed 0.0 => 1.0
% WARNING : Bus 39 : basekv changed 0.0 => 1.0
% WARNING : Bus 40 : basekv changed 0.0 => 1.0
% WARNING : Bus 41 : basekv changed 0.0 => 1.0
% WARNING : Bus 42 : basekv changed 0.0 => 1.0
% WARNING : Bus 43 : basekv changed 0.0 => 1.0
% WARNING : Bus 44 : basekv changed 0.0 => 1.0
% WARNING : Bus 45 : basekv changed 0.0 => 1.0
% WARNING : Bus 46 : basekv changed 0.0 => 1.0
% WARNING : Bus 47 : basekv changed 0.0 => 1.0
% WARNING : Bus 48 : basekv changed 0.0 => 1.0
% WARNING : Bus 49 : basekv changed 0.0 => 1.0
% WARNING : Bus 50 : basekv changed 0.0 => 1.0
% WARNING : Bus 51 : basekv changed 0.0 => 1.0
% WARNING : Bus 52 : basekv changed 0.0 => 1.0
% WARNING : Bus 53 : basekv changed 0.0 => 1.0
% WARNING : Bus 54 : basekv changed 0.0 => 1.0
% WARNING : Bus 55 : basekv changed 0.0 => 1.0
% WARNING : Bus 56 : basekv changed 0.0 => 1.0
% WARNING : Bus 57 : basekv changed 0.0 => 1.0
% INFO    : 
% INFO    : === Transformer Setting Replacement Notes ===
% INFO    : 
% INFO    : === Line Capacity Stat Model Notes ===
% WARNING : Missing data for branch flow stat model on line 1-2 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0083 x=0.028
% INFO    : Updated Thermal Rating: on line 1-2 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 1005
% WARNING : Missing data for branch flow stat model on line 2-3 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0298 x=0.085
% INFO    : Updated Thermal Rating: on line 2-3 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 326
% WARNING : Missing data for branch flow stat model on line 3-4 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0112 x=0.0366
% INFO    : Updated Thermal Rating: on line 3-4 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 767
% WARNING : Missing data for branch flow stat model on line 4-5 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0625 x=0.132
% INFO    : Updated Thermal Rating: on line 4-5 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 201
% WARNING : Missing data for branch flow stat model on line 4-6 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.043 x=0.148
% INFO    : Updated Thermal Rating: on line 4-6 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 191
% WARNING : Missing data for branch flow stat model on line 6-7 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.02 x=0.102
% INFO    : Updated Thermal Rating: on line 6-7 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 283
% WARNING : Missing data for branch flow stat model on line 6-8 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0339 x=0.173
% INFO    : Updated Thermal Rating: on line 6-8 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 167
% WARNING : Missing data for branch flow stat model on line 8-9 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0099 x=0.0505
% INFO    : Updated Thermal Rating: on line 8-9 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 570
% WARNING : Missing data for branch flow stat model on line 9-10 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0369 x=0.1679
% INFO    : Updated Thermal Rating: on line 9-10 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 171
% WARNING : Missing data for branch flow stat model on line 9-11 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0258 x=0.0848
% INFO    : Updated Thermal Rating: on line 9-11 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 331
% WARNING : Missing data for branch flow stat model on line 9-12 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0648 x=0.295
% INFO    : Updated Thermal Rating: on line 9-12 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 98
% WARNING : Missing data for branch flow stat model on line 9-13 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0481 x=0.158
% INFO    : Updated Thermal Rating: on line 9-13 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 178
% WARNING : Missing data for branch flow stat model on line 13-14 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0132 x=0.0434
% INFO    : Updated Thermal Rating: on line 13-14 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 647
% WARNING : Missing data for branch flow stat model on line 13-15 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0269 x=0.0869
% INFO    : Updated Thermal Rating: on line 13-15 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 323
% WARNING : Missing data for branch flow stat model on line 1-15 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0178 x=0.091
% INFO    : Updated Thermal Rating: on line 1-15 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 317
% WARNING : Missing data for branch flow stat model on line 1-16 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0454 x=0.206
% INFO    : Updated Thermal Rating: on line 1-16 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 140
% WARNING : Missing data for branch flow stat model on line 1-17 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0238 x=0.108
% INFO    : Updated Thermal Rating: on line 1-17 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 266
% WARNING : Missing data for branch flow stat model on line 3-15 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0162 x=0.053
% INFO    : Updated Thermal Rating: on line 3-15 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 530
% WARNING : Missing data for branch flow stat model on line 4-18 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=0.555
% INFO    : Updated Thermal Rating: on transformer 4-18 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 53
% WARNING : Missing data for branch flow stat model on line 4-18 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=0.43
% INFO    : Updated Thermal Rating: on transformer 4-18 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 69
% WARNING : Missing data for branch flow stat model on line 5-6 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0302 x=0.0641
% INFO    : Updated Thermal Rating: on line 5-6 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 414
% WARNING : Missing data for branch flow stat model on line 7-8 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0139 x=0.0712
% INFO    : Updated Thermal Rating: on line 7-8 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 405
% WARNING : Missing data for branch flow stat model on line 10-12 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0277 x=0.1262
% INFO    : Updated Thermal Rating: on line 10-12 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 228
% WARNING : Missing data for branch flow stat model on line 11-13 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0223 x=0.0732
% INFO    : Updated Thermal Rating: on line 11-13 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 384
% WARNING : Missing data for branch flow stat model on line 12-13 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0178 x=0.058
% INFO    : Updated Thermal Rating: on line 12-13 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 484
% WARNING : Missing data for branch flow stat model on line 12-16 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.018 x=0.0813
% INFO    : Updated Thermal Rating: on line 12-16 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 353
% WARNING : Missing data for branch flow stat model on line 12-17 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0397 x=0.179
% INFO    : Updated Thermal Rating: on line 12-17 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 160
% WARNING : Missing data for branch flow stat model on line 14-15 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0171 x=0.0547
% INFO    : Updated Thermal Rating: on line 14-15 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 512
% WARNING : Missing data for branch flow stat model on line 18-19 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.461 x=0.685
% INFO    : Updated Thermal Rating: on line 18-19 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 36
% WARNING : Missing data for branch flow stat model on line 19-20 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.283 x=0.434
% INFO    : Updated Thermal Rating: on line 19-20 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 57
% WARNING : Missing data for branch flow stat model on line 21-20 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=0.7767
% INFO    : Updated Thermal Rating: on transformer 21-20 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 38
% WARNING : Missing data for branch flow stat model on line 21-22 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0736 x=0.117
% INFO    : Updated Thermal Rating: on line 21-22 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 213
% WARNING : Missing data for branch flow stat model on line 22-23 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0099 x=0.0152
% INFO    : Updated Thermal Rating: on line 22-23 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 1617
% WARNING : Missing data for branch flow stat model on line 23-24 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.166 x=0.256
% INFO    : Updated Thermal Rating: on line 23-24 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 97
% WARNING : Missing data for branch flow stat model on line 24-25 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=1.182
% INFO    : Updated Thermal Rating: on transformer 24-25 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 25
% WARNING : Missing data for branch flow stat model on line 24-25 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=1.23
% INFO    : Updated Thermal Rating: on transformer 24-25 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 24
% WARNING : Missing data for branch flow stat model on line 24-26 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=0.0473
% INFO    : Updated Thermal Rating: on transformer 24-26 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 621
% WARNING : Missing data for branch flow stat model on line 26-27 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.165 x=0.254
% INFO    : Updated Thermal Rating: on line 26-27 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 97
% WARNING : Missing data for branch flow stat model on line 27-28 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0618 x=0.0954
% INFO    : Updated Thermal Rating: on line 27-28 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 259
% WARNING : Missing data for branch flow stat model on line 28-29 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0418 x=0.0587
% INFO    : Updated Thermal Rating: on line 28-29 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 408
% WARNING : Missing data for branch flow stat model on line 7-29 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=0.0648
% INFO    : Updated Thermal Rating: on transformer 7-29 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 453
% WARNING : Missing data for branch flow stat model on line 25-30 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.135 x=0.202
% INFO    : Updated Thermal Rating: on line 25-30 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 121
% WARNING : Missing data for branch flow stat model on line 30-31 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.326 x=0.497
% INFO    : Updated Thermal Rating: on line 30-31 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 50
% WARNING : Missing data for branch flow stat model on line 31-32 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.507 x=0.755
% INFO    : Updated Thermal Rating: on line 31-32 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 33
% WARNING : Missing data for branch flow stat model on line 32-33 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0392 x=0.036
% INFO    : Updated Thermal Rating: on line 32-33 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 552
% WARNING : Missing data for branch flow stat model on line 34-32 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=0.953
% INFO    : Updated Thermal Rating: on transformer 34-32 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 31
% WARNING : Missing data for branch flow stat model on line 34-35 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.052 x=0.078
% INFO    : Updated Thermal Rating: on line 34-35 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 313
% WARNING : Missing data for branch flow stat model on line 35-36 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.043 x=0.0537
% INFO    : Updated Thermal Rating: on line 35-36 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 427
% WARNING : Missing data for branch flow stat model on line 36-37 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.029 x=0.0366
% INFO    : Updated Thermal Rating: on line 36-37 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 629
% WARNING : Missing data for branch flow stat model on line 37-38 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0651 x=0.1009
% INFO    : Updated Thermal Rating: on line 37-38 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 245
% WARNING : Missing data for branch flow stat model on line 37-39 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0239 x=0.0379
% INFO    : Updated Thermal Rating: on line 37-39 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 655
% WARNING : Missing data for branch flow stat model on line 36-40 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.03 x=0.0466
% INFO    : Updated Thermal Rating: on line 36-40 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 530
% WARNING : Missing data for branch flow stat model on line 22-38 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0192 x=0.0295
% INFO    : Updated Thermal Rating: on line 22-38 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 834
% WARNING : Missing data for branch flow stat model on line 11-41 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=0.749
% INFO    : Updated Thermal Rating: on transformer 11-41 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 40
% WARNING : Missing data for branch flow stat model on line 41-42 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.207 x=0.352
% INFO    : Updated Thermal Rating: on line 41-42 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 72
% WARNING : Missing data for branch flow stat model on line 41-43 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=0.412
% INFO    : Updated Thermal Rating: on line 41-43 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 72
% WARNING : Missing data for branch flow stat model on line 38-44 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0289 x=0.0585
% INFO    : Updated Thermal Rating: on line 38-44 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 450
% WARNING : Missing data for branch flow stat model on line 15-45 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=0.1042
% INFO    : Updated Thermal Rating: on transformer 15-45 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 282
% WARNING : Missing data for branch flow stat model on line 14-46 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=0.0735
% INFO    : Updated Thermal Rating: on transformer 14-46 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 400
% WARNING : Missing data for branch flow stat model on line 46-47 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.023 x=0.068
% INFO    : Updated Thermal Rating: on line 46-47 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 409
% WARNING : Missing data for branch flow stat model on line 47-48 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0182 x=0.0233
% INFO    : Updated Thermal Rating: on line 47-48 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 993
% WARNING : Missing data for branch flow stat model on line 48-49 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0834 x=0.129
% INFO    : Updated Thermal Rating: on line 48-49 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 191
% WARNING : Missing data for branch flow stat model on line 49-50 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0801 x=0.128
% INFO    : Updated Thermal Rating: on line 49-50 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 195
% WARNING : Missing data for branch flow stat model on line 50-51 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.1386 x=0.22
% INFO    : Updated Thermal Rating: on line 50-51 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 113
% WARNING : Missing data for branch flow stat model on line 10-51 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=0.0712
% INFO    : Updated Thermal Rating: on transformer 10-51 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 412
% WARNING : Missing data for branch flow stat model on line 13-49 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=0.191
% INFO    : Updated Thermal Rating: on transformer 13-49 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 154
% WARNING : Missing data for branch flow stat model on line 29-52 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.1442 x=0.187
% INFO    : Updated Thermal Rating: on line 29-52 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 125
% WARNING : Missing data for branch flow stat model on line 52-53 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0762 x=0.0984
% INFO    : Updated Thermal Rating: on line 52-53 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 236
% WARNING : Missing data for branch flow stat model on line 53-54 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.1878 x=0.232
% INFO    : Updated Thermal Rating: on line 53-54 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 99
% WARNING : Missing data for branch flow stat model on line 54-55 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.1732 x=0.2265
% INFO    : Updated Thermal Rating: on line 54-55 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 103
% WARNING : Missing data for branch flow stat model on line 11-43 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=0.153
% INFO    : Updated Thermal Rating: on transformer 11-43 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 192
% WARNING : Missing data for branch flow stat model on line 44-45 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0624 x=0.1242
% INFO    : Updated Thermal Rating: on line 44-45 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 212
% WARNING : Missing data for branch flow stat model on line 40-56 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=1.195
% INFO    : Updated Thermal Rating: on transformer 40-56 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 25
% WARNING : Missing data for branch flow stat model on line 56-41 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.553 x=0.549
% INFO    : Updated Thermal Rating: on line 56-41 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 38
% WARNING : Missing data for branch flow stat model on line 56-42 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.2125 x=0.354
% INFO    : Updated Thermal Rating: on line 56-42 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 72
% WARNING : Missing data for branch flow stat model on line 39-57 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=1.355
% INFO    : Updated Thermal Rating: on transformer 39-57 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 22
% WARNING : Missing data for branch flow stat model on line 57-56 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.174 x=0.26
% INFO    : Updated Thermal Rating: on line 57-56 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 94
% WARNING : Missing data for branch flow stat model on line 38-49 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.115 x=0.177
% INFO    : Updated Thermal Rating: on line 38-49 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 139
% WARNING : Missing data for branch flow stat model on line 38-48 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0312 x=0.0482
% INFO    : Updated Thermal Rating: on line 38-48 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 511
% WARNING : Missing data for branch flow stat model on line 9-55 using max current model : from_basekv=1.0 to_basekv=1.0 r=0.0 x=0.1205
% INFO    : Updated Thermal Rating: on transformer 9-55 : Rate A, Rate B, Rate C , 9900.0, 0.0, 0.0 -> 244
% INFO    : 
% INFO    : === Line Capacity Monotonicity Notes ===
% INFO    : 
% INFO    : === Voltage Setpoint Replacement Notes ===
% INFO    : Bus 1	: V=1.04, theta=0.0 -> V=1.0, theta=0.0
% INFO    : Bus 2	: V=1.01, theta=-1.18 -> V=1.0, theta=0.0
% INFO    : Bus 3	: V=0.985, theta=-5.97 -> V=1.0, theta=0.0
% INFO    : Bus 4	: V=0.981, theta=-7.32 -> V=1.0, theta=0.0
% INFO    : Bus 5	: V=0.976, theta=-8.52 -> V=1.0, theta=0.0
% INFO    : Bus 6	: V=0.98, theta=-8.65 -> V=1.0, theta=0.0
% INFO    : Bus 7	: V=0.984, theta=-7.58 -> V=1.0, theta=0.0
% INFO    : Bus 8	: V=1.005, theta=-4.45 -> V=1.0, theta=0.0
% INFO    : Bus 9	: V=0.98, theta=-9.56 -> V=1.0, theta=0.0
% INFO    : Bus 10	: V=0.986, theta=-11.43 -> V=1.0, theta=0.0
% INFO    : Bus 11	: V=0.974, theta=-10.17 -> V=1.0, theta=0.0
% INFO    : Bus 12	: V=1.015, theta=-10.46 -> V=1.0, theta=0.0
% INFO    : Bus 13	: V=0.979, theta=-9.79 -> V=1.0, theta=0.0
% INFO    : Bus 14	: V=0.97, theta=-9.33 -> V=1.0, theta=0.0
% INFO    : Bus 15	: V=0.988, theta=-7.18 -> V=1.0, theta=0.0
% INFO    : Bus 16	: V=1.013, theta=-8.85 -> V=1.0, theta=0.0
% INFO    : Bus 17	: V=1.017, theta=-5.39 -> V=1.0, theta=0.0
% INFO    : Bus 18	: V=1.001, theta=-11.71 -> V=1.0, theta=0.0
% INFO    : Bus 19	: V=0.97, theta=-13.2 -> V=1.0, theta=0.0
% INFO    : Bus 20	: V=0.964, theta=-13.41 -> V=1.0, theta=0.0
% INFO    : Bus 21	: V=1.008, theta=-12.89 -> V=1.0, theta=0.0
% INFO    : Bus 22	: V=1.01, theta=-12.84 -> V=1.0, theta=0.0
% INFO    : Bus 23	: V=1.008, theta=-12.91 -> V=1.0, theta=0.0
% INFO    : Bus 24	: V=0.999, theta=-13.25 -> V=1.0, theta=0.0
% INFO    : Bus 25	: V=0.982, theta=-18.13 -> V=1.0, theta=0.0
% INFO    : Bus 26	: V=0.959, theta=-12.95 -> V=1.0, theta=0.0
% INFO    : Bus 27	: V=0.982, theta=-11.48 -> V=1.0, theta=0.0
% INFO    : Bus 28	: V=0.997, theta=-10.45 -> V=1.0, theta=0.0
% INFO    : Bus 29	: V=1.01, theta=-9.75 -> V=1.0, theta=0.0
% INFO    : Bus 30	: V=0.962, theta=-18.68 -> V=1.0, theta=0.0
% INFO    : Bus 31	: V=0.936, theta=-19.34 -> V=1.0, theta=0.0
% INFO    : Bus 32	: V=0.949, theta=-18.46 -> V=1.0, theta=0.0
% INFO    : Bus 33	: V=0.947, theta=-18.5 -> V=1.0, theta=0.0
% INFO    : Bus 34	: V=0.959, theta=-14.1 -> V=1.0, theta=0.0
% INFO    : Bus 35	: V=0.966, theta=-13.86 -> V=1.0, theta=0.0
% INFO    : Bus 36	: V=0.976, theta=-13.59 -> V=1.0, theta=0.0
% INFO    : Bus 37	: V=0.985, theta=-13.41 -> V=1.0, theta=0.0
% INFO    : Bus 38	: V=1.013, theta=-12.71 -> V=1.0, theta=0.0
% INFO    : Bus 39	: V=0.983, theta=-13.46 -> V=1.0, theta=0.0
% INFO    : Bus 40	: V=0.973, theta=-13.62 -> V=1.0, theta=0.0
% INFO    : Bus 41	: V=0.996, theta=-14.05 -> V=1.0, theta=0.0
% INFO    : Bus 42	: V=0.966, theta=-15.5 -> V=1.0, theta=0.0
% INFO    : Bus 43	: V=1.01, theta=-11.33 -> V=1.0, theta=0.0
% INFO    : Bus 44	: V=1.017, theta=-11.86 -> V=1.0, theta=0.0
% INFO    : Bus 45	: V=1.036, theta=-9.25 -> V=1.0, theta=0.0
% INFO    : Bus 46	: V=1.05, theta=-11.89 -> V=1.0, theta=0.0
% INFO    : Bus 47	: V=1.033, theta=-12.49 -> V=1.0, theta=0.0
% INFO    : Bus 48	: V=1.027, theta=-12.59 -> V=1.0, theta=0.0
% INFO    : Bus 49	: V=1.036, theta=-12.92 -> V=1.0, theta=0.0
% INFO    : Bus 50	: V=1.023, theta=-13.39 -> V=1.0, theta=0.0
% INFO    : Bus 51	: V=1.052, theta=-12.52 -> V=1.0, theta=0.0
% INFO    : Bus 52	: V=0.98, theta=-11.47 -> V=1.0, theta=0.0
% INFO    : Bus 53	: V=0.971, theta=-12.23 -> V=1.0, theta=0.0
% INFO    : Bus 54	: V=0.996, theta=-11.69 -> V=1.0, theta=0.0
% INFO    : Bus 55	: V=1.031, theta=-10.78 -> V=1.0, theta=0.0
% INFO    : Bus 56	: V=0.968, theta=-16.04 -> V=1.0, theta=0.0
% INFO    : Bus 57	: V=0.965, theta=-16.56 -> V=1.0, theta=0.0
% INFO    : 
% INFO    : === Generator Setpoint Replacement Notes ===
% INFO    : Gen at bus 1	: Pg=128.9, Qg=-16.1 -> Pg=122.5, Qg=0.0
% INFO    : Gen at bus 1	: Vg=1.04 -> Vg=1.0
% INFO    : Gen at bus 2	: Pg=0.0, Qg=-0.8 -> Pg=0.0, Qg=16.5
% INFO    : Gen at bus 2	: Vg=1.01 -> Vg=1.0
% INFO    : Gen at bus 3	: Pg=40.0, Qg=-1.0 -> Pg=30.0, Qg=10.0
% INFO    : Gen at bus 3	: Vg=0.985 -> Vg=1.0
% INFO    : Gen at bus 6	: Pg=0.0, Qg=0.8 -> Pg=0.0, Qg=8.5
% INFO    : Gen at bus 6	: Vg=0.98 -> Vg=1.0
% INFO    : Gen at bus 8	: Pg=450.0, Qg=62.1 -> Pg=579.5, Qg=30.0
% INFO    : Gen at bus 8	: Vg=1.005 -> Vg=1.0
% INFO    : Gen at bus 9	: Pg=0.0, Qg=2.2 -> Pg=0.0, Qg=3.0
% INFO    : Gen at bus 9	: Vg=0.98 -> Vg=1.0
% INFO    : Gen at bus 12	: Pg=310.0, Qg=128.5 -> Pg=259.5, Qg=2.5
% INFO    : Gen at bus 12	: Vg=1.015 -> Vg=1.0
% INFO    : 
% INFO    : === Writing Matpower Case File Notes ===
