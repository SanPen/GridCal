Benchmarks
===========



Linear algebra frameworks benchmark
-----------------------------------

IEEE 39 1-year time series
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The experiment is to test the time taken by the time series simulation using different linear algebra solvers.

The power flow tolerance is ser to 1e-4.


The time in seconds taken using each of the solvers is:


+---------+------------------+------------------+------------------+------------------+------------------+
|         | KLU              | BLAS/LAPACK      | ILU              | SuperLU          | Pardiso          |
+=========+==================+==================+==================+==================+==================+
| Test 1  | 82.0306398868561 | 82.1049809455872 | 81.7956540584564 | 82.8895554542542 | 93.2362771034241 |
| Test 2  | 80.2231616973877 | 80.8419146537781 | 81.7140426635742 | 81.3713464736938 | 95.2913007736206 |
| Test 3  | 79.5343339443207 | 82.3211221694946 | 82.7529213428497 | 80.9804055690765 | 92.6268711090088 |
| Test 4  | 80.0667154788971 | 82.6606991291046 | 82.1418635845184 | 80.178496837616  | 97.6009163856506 |
| Test 5  | 80.0720291137695 | 80.5129723548889 | 81.9473338127136 | 80.0363531112671 | 93.3938195705414 |
+---------+------------------+------------------+------------------+------------------+------------------+
| Average | 80.3853760242462 | 81.6883378505707 | 82.0703630924225 | 81.0912314891815 | 94.4298369884491 |
+---------+------------------+------------------+------------------+------------------+------------------+


2869 Pegase 1-week time series
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The experiment is to test the time taken by the time series simulation using different linear algebra solvers.

The power flow tolerance is ser to 1e-4.


The time in seconds taken using each of the solvers is:


+---------+------------------+------------------+------------------+------------------+------------------+
|         | KLU              | BLAS/LAPACK      | ILU              | SuperLU          | Pardiso          |
+=========+==================+==================+==================+==================+==================+
| Test 1  | 2.46547317504882 | 2.50752806663513 | 2.52735018730163 | 2.48413443565368 | 2.54547953605651 |
| Test 2  | 2.35307431221008 | 2.31241440773010 | 2.36424255371093 | 2.32830643653869 | 2.59090781211853 |
| Test 3  | 2.40140151977539 | 2.42792844772338 | 2.46322917938232 | 2.46966910362243 | 2.46686577796936 |
| Test 4  | 2.33513951301574 | 2.31270241737365 | 2.34093046188354 | 2.33488821983337 | 2.42691206932067 |
| Test 5  | 2.31796050071716 | 2.32209181785583 | 2.45891189575195 | 2.33409214019775 | 2.51999592781066 |
+---------+------------------+------------------+------------------+------------------+------------------+
| Average | 2.37460980415344 | 2.37653303146362 | 2.43093285560608 | 2.39021806716919 | 2.51003222465515 |
+---------+------------------+------------------+------------------+------------------+------------------+

So from the light of these tests the solvers are roughly equivalent except the Pardiso one with is
worse than the others for these type of simulations.