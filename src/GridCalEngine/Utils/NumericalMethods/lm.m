function  [X, info, perf] = marquardt(fun,fpar, x0, opts)
%MARQUARDT  Marquardt's method for least squares.
%  Find  xm = argmin{F(x)} , where  x  is an n-vector and
%  F(x) = .5 * sum(f_i(x)^2) .
%  The functions  f_i(x) (i=1,...,m) and the Jacobian matrix  J(x)
%  (with elements  J(i,j) = Df_i/Dx_j ) must be given by a MATLAB
%  function with declaration
%            function  [f, J] = fun(x, fpar)
%  fpar  can e.g. be an array with coordinates of data points,
%  or it may be dummy.
%
%  Call
%      [X, info {, perf}] = Marquardt(fun,fpar, x0, opts)
%
%  Input parameters
%  fun  :  String with the name of the function.
%  fpar :  Parameters of the function.  May be empty.
%  x0   :  Starting guess for  x .
%  opts :  Vector with four elements:
%          opts(1)  used in starting value for Marquardt parameter:
%              mu = opts(1) * max(A0(i,i))  with  A0 = J(x0)' J(x0)
%          opts(2:4)  used in stopping criteria:
%              ||F'||inf <= opts(2)                     or
%              ||dx||2 <= opts(3)*(opts(3) + ||x||2)    or
%              no. of iteration steps exceeds  opts(4) .
%
%  Output parameters
%  X    :  If  perf  is present, then array, holding the iterates
%          columnwise.  Otherwise, computed solution vector.
%  info :  Performance information, vector with 6 elements:
%          info(1:4) = final values of
%              [F(x)  ||F'||inf  ||dx||2  mu/max(A(i,i))] ,
%            where  A = J(x)' J(x) .
%          info(5) = no. of iteration steps
%          info(6) = 1 : Stopped by small gradient
%                    2 :  Stopped by small x-step
%                    3 :  Stopped by  kmax
%                    4 :  Singular matrix.  Restart from current
%                         x  with increased value for  mu .
%  perf :  (optional). If present, then array, holding
%            perf(1,:) = values of  F(x)
%            perf(2,:) = values of  || F'(x) ||inf
%            perf(3,:) = mu-values.

%  Hans Bruun Nielsen,  IMM, DTU.  99.06.08 / 00.09.05 / 01.10.02

[x,n, f,J] = check(fun,fpar,x0,opts);
%  Initial values
A = J'*J;
g = J'*f;
F = (f'*f)/2;
ng = norm(g,inf);
mu = opts(1) * max(diag(A));    kmax = opts(4);
Trace = nargout > 2;
if  Trace
    X = x*ones(1,kmax+1);
    perf = [F; ng; mu]*ones(1,kmax+1);
end
k = 1;   nu = 2;   nh = 0;   stop = 0;

while   ~stop
    if  ng <= opts(2),  stop = 1;
    else
        h = (A + mu*eye(n))\(-g);
        nh = norm(h);
        nx = opts(3) + norm(x);
        if      nh <= opts(3)*nx,  stop = 2;
        elseif  nh >= nx/eps,   stop = 4; end    % Almost singular ?
    end
    if  ~stop
        xnew = x + h;
        h = xnew - x;
        dL = (h'*(mu*h - g))/2;
        [fn,Jn] = feval(fun, xnew,fpar);
        Fn = (fn'*fn)/2;
        dF = F - Fn;
        if  (dL > 0) & (dF > 0)               % Update x and modify mu
            x = xnew;
            F = Fn;
            J = Jn;
            f = fn;
            A = J'*J;
            g = J'*f;
            ng = norm(g,inf);
            mu = mu * max(1/3, 1 - (2*dF/dL - 1)^3);
            nu = 2;
        else                                  % Same  x, increase  mu
            mu = mu*nu;  nu = 2*nu;
        end
        k = k + 1;
        if  Trace,  X(:,k) = x;   perf(:,k) = [F ng mu]'; end
        if  k > kmax,  stop = 3; end
    end
end
%  Set return values
if  Trace
    X = X(:,1:k);   perf = perf(:,1:k);
else,  X = x;  end
info = [F  ng  nh  mu/max(diag(A))  k-1  stop];

% ==========  auxiliary function  =================================

function  [x,n, f,J] = check(fun,fpar,x0,opts)
%  Check function call
sx = size(x0);   n = max(sx);
if  (min(sx) > 1)
    error('x0  should be a vector'), end
x = x0(:);   [f J] = feval(fun,x,fpar);
sf = size(f);   sJ = size(J);
if  sf(2) ~= 1
    error('f  must be a column vector'), end
if  sJ(1) ~= sf(1)
    error('row numbers in  f  and  J  do not match'), end
if  sJ(2) ~= n
    error('number of columns in  J  does not match  x'), end
%  Thresholds
if  length(opts) < 4
    error('opts  must have 4 elements'), end
if  length(find(opts(1:4) <= 0))
    error('The elements in  opts  must be strictly positive'), end