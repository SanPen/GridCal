import os
import numpy as np
import ctypes
from ctypes import c_int, c_char_p, c_void_p, byref, POINTER, c_double


CPX_STAT_NUM_BEST = 6
CPX_STAT_OPTIMAL = 1
CPX_STAT_FEASIBLE = 23
CPX_AUTO = -1
CPX_ON = 1
CPX_OFF = 0
CPX_MAX = -1
CPX_MIN = 1
CPXPARAM_ScreenOutput = 1035


def find_dynamic_library(candidates, dll_name_hint):
    """
    Find the dynamic library by searching the given candidate paths.
    """
    extensions = {
        'nt': '.dll',
        'posix': '.so',
        'Darwin': '.dylib'
    }
    dll_extension = extensions.get(os.name)

    for candidate in candidates:
        dll_path = os.path.join(candidate, f"{dll_name_hint}{dll_extension}")
        if os.path.isfile(dll_path):
            return dll_path

    return None


class CplexLib:
    """
    CPLEX MIP interface
    """

    def __init__(self):
        # Detect platform and set library search paths accordingly
        if os.name == 'nt':  # Windows
            candidates = [""]
            dll_name_hint = "cplex"
        elif os.uname().sysname == 'Darwin':  # macOS
            candidates = ["", "/Applications/FICO Xpress/Xpress Workbench.app/Contents/Resources/xpressmp/lib"]
            dll_name_hint = "libcplex"
        elif os.name == 'posix':  # Linux
            candidates = ["", "/opt/ibm/ILOG/CPLEX_Enterprise_Server1210/CPLEX_Studio/cplex/bin/x86-64_linux"]
            dll_name_hint = "libcplex"
        else:
            raise RuntimeError("Unsupported platform")

        # Fetch all environment variables
        env_vars = os.environ

        # Add paths from CPLEX_STUDIO_BINARIES environment variable if it exists
        for key, value in env_vars.items():
            if key.startswith("CPLEX_STUDIO_BINARIES"):
                if os.name == 'nt':
                    paths = value.split(";")
                else:  # Linux and macOS
                    paths = value.split(":")
                candidates.extend(paths)

        # Find the dynamic library based on candidates
        dll_path = find_dynamic_library(candidates, dll_name_hint)

        # Try loading the library
        self._is_available = dll_path is not None

        if self._is_available:
            # Load the library
            self._lib = ctypes.CDLL(dll_path)

            # Link the CPLEX functions
            ok = self.link_functions()

            if ok:
                # Initialize the CPLEX environment
                self._env = c_void_p()
                status = c_int(0)
                self._env = self._lib.CPXopenCPLEX(byref(status))

                if self._env is None:
                    errmsg = ctypes.create_string_buffer(512)  # Size of CPXMESSAGEBUFSIZE
                    self._lib.CPXgeterrorstring(self._env, status.value, errmsg)
                    print(f"Could not open CPLEX environment: {errmsg.value.decode()}")
                    self._is_licensed = False
                else:
                    version = self._lib.CPXversion(self._env)
                    self._version = version.decode('utf-8') if isinstance(version, bytes) else str(version)
                    self._is_licensed = True
            else:
                self._is_available = False
                self._is_licensed = False
        else:
            self._is_licensed = False

    def link_functions(self):
        """
        Load all required CPLEX functions from the shared library.
        """
        try:
            self.CPXopenCPLEX = self._lib.CPXopenCPLEX
            self.CPXopenCPLEX.restype = c_void_p
            self.CPXopenCPLEX.argtypes = [ctypes.POINTER(c_int)]

            self.CPXgeterrorstring = self._lib.CPXgeterrorstring
            self.CPXgeterrorstring.restype = c_char_p
            self.CPXgeterrorstring.argtypes = [c_void_p, c_int, c_char_p]

            self.CPXsetintparam = self._lib.CPXsetintparam
            self.CPXsetintparam.restype = c_int
            self.CPXsetintparam.argtypes = [c_void_p, c_int, c_int]

            self.CPXcreateprob = self._lib.CPXcreateprob
            self.CPXcreateprob.restype = c_void_p
            self.CPXcreateprob.argtypes = [c_void_p, ctypes.POINTER(c_int), c_char_p]

            self.CPXcopylp = self._lib.CPXcopylp
            self.CPXcopylp.restype = c_int
            self.CPXcopylp.argtypes = [
                c_void_p, c_void_p, c_int, c_int, c_int,
                POINTER(c_double), POINTER(c_double), c_char_p,
                POINTER(c_int), POINTER(c_int), POINTER(c_int),
                POINTER(c_double), POINTER(c_double), POINTER(c_double), POINTER(c_double)
            ]

            self.CPXcopyctype = self._lib.CPXcopyctype
            self.CPXcopyctype.restype = c_int
            self.CPXcopyctype.argtypes = [c_void_p, c_void_p, c_char_p]

            self.CPXmipopt = self._lib.CPXmipopt
            self.CPXmipopt.restype = c_int
            self.CPXmipopt.argtypes = [c_void_p, c_void_p]

            self.CPXlpopt = self._lib.CPXlpopt
            self.CPXlpopt.restype = c_int
            self.CPXlpopt.argtypes = [c_void_p, c_void_p]

            self.CPXgetstat = self._lib.CPXgetstat
            self.CPXgetstat.restype = c_int
            self.CPXgetstat.argtypes = [c_void_p, c_void_p]

            self.CPXgetobjval = self._lib.CPXgetobjval
            self.CPXgetobjval.restype = c_int
            self.CPXgetobjval.argtypes = [c_void_p, c_void_p, POINTER(c_double)]

            self.CPXgetnumrows = self._lib.CPXgetnumrows
            self.CPXgetnumrows.restype = c_int
            self.CPXgetnumrows.argtypes = [c_void_p, c_void_p]

            self.CPXgetnumcols = self._lib.CPXgetnumcols
            self.CPXgetnumcols.restype = c_int
            self.CPXgetnumcols.argtypes = [c_void_p, c_void_p]

            self.CPXgetx = self._lib.CPXgetx
            self.CPXgetx.restype = c_int
            self.CPXgetx.argtypes = [c_void_p, c_void_p, POINTER(c_double), c_int, c_int]

            self.CPXgetslack = self._lib.CPXgetslack
            self.CPXgetslack.restype = c_int
            self.CPXgetslack.argtypes = [c_void_p, c_void_p, POINTER(c_double), c_int, c_int]

            self.CPXwriteprob = self._lib.CPXwriteprob
            self.CPXwriteprob.restype = c_int
            self.CPXwriteprob.argtypes = [c_void_p, c_void_p, c_char_p, c_char_p]

            self.CPXfreeprob = self._lib.CPXfreeprob
            self.CPXfreeprob.restype = c_int
            self.CPXfreeprob.argtypes = [c_void_p, POINTER(c_void_p)]

            self.CPXcloseCPLEX = self._lib.CPXcloseCPLEX
            self.CPXcloseCPLEX.restype = c_int
            self.CPXcloseCPLEX.argtypes = [POINTER(c_void_p)]

            self.CPXversion = self._lib.CPXversion
            self.CPXversion.restype = c_char_p
            self.CPXversion.argtypes = [c_void_p]

            self.CPXnewcols = self._lib.CPXnewcols
            self.CPXnewcols.restype = c_int
            self.CPXnewcols.argtypes = [
                c_void_p, c_void_p, c_int,
                POINTER(c_double), POINTER(c_double), POINTER(c_double),
                c_char_p, POINTER(c_char_p)
            ]

            self.CPXaddrows = self._lib.CPXaddrows
            self.CPXaddrows.restype = c_int
            self.CPXaddrows.argtypes = [
                c_void_p, c_void_p, c_int, c_int, c_int,
                POINTER(c_double), c_char_p,
                POINTER(c_int), POINTER(c_int),
                POINTER(c_double), POINTER(c_char_p), POINTER(c_char_p)
            ]

            self.CPXnewrows = self._lib.CPXnewrows
            self.CPXnewrows.restype = c_int
            self.CPXnewrows.argtypes = [
                c_void_p, c_void_p, c_int,
                POINTER(c_double), c_char_p,
                POINTER(c_double), POINTER(c_char_p)
            ]

            self.CPXsolution = self._lib.CPXsolution
            self.CPXsolution.restype = c_int
            self.CPXsolution.argtypes = [
                c_void_p, c_void_p, POINTER(c_int),
                POINTER(c_double), POINTER(c_double),
                POINTER(c_double), POINTER(c_double),
                POINTER(c_double)
            ]

            self.CPXchgobjsen = self._lib.CPXchgobjsen
            self.CPXchgobjsen.restype = c_int
            self.CPXchgobjsen.argtypes = [c_void_p, c_void_p, c_int]

            self.CPXchgrngval = self._lib.CPXchgrngval
            self.CPXchgrngval.restype = c_int
            self.CPXchgrngval.argtypes = [
                c_void_p, c_void_p, c_int,
                POINTER(c_int), POINTER(c_double)
            ]

            return True
        except AttributeError as e:
            print(f"Error linking functions: {e}")
            return False

    def __del__(self):
        if self._env is not None:
            status = self.CPXcloseCPLEX(byref(self._env))

            if status:
                errmsg = ctypes.create_string_buffer(512)  # Size of CPXMESSAGEBUFSIZE
                self.CPXgeterrorstring(self._env, status, errmsg)
                print(f"Could not close CPLEX environment: {errmsg.value.decode()}")

        # Unlink the dynamic library
        if hasattr(self, '_lib'):
            if os.name == 'nt':  # Windows
                if self._lib:
                    ctypes.windll.kernel32.FreeLibrary(self._lib._handle)
            else:  # Linux or macOS
                if self._lib:
                    ctypes.cdll.LoadLibrary('libdl').dlclose(self._lib._handle)

    def get_env(self):
        """Returns the CPLEX environment pointer."""
        return self._env

    def is_licensed(self):
        """Returns whether the CPLEX environment is licensed."""
        return self._is_licensed

    def solve(self, problem, verbose=True):
        """

        :param problem:
        :param verbose:
        :return:
        """
        assert problem.getObjectiveFunction().size() > 0, "Objective function is empty."

        # Get a map of the variables
        vars_map = problem.getVarsPositionMap()

        num_cols = len(problem.getVars())
        num_rows = len(problem.getConstraints())
        num_nz = problem.getNnz()

        # Declare results
        res = LpResult(num_cols, num_rows)
        res.setVarRanges(problem.getRanges())
        res.setConstraintRanges(problem.getConstraintRanges())

        # Create the CPLEX model
        cplex_model = ctypes.c_void_p()
        err = ctypes.c_int()

        # Set output verbosity
        self.CPXsetintparam(self._env, CPXPARAM_ScreenOutput, CPX_ON if verbose else CPX_OFF)

        # Create the problem
        cplex_model = self.CPXcreateprob(self._env, byref(err), problem.getName().encode('utf-8'))
        if not cplex_model:
            self.handle_error(err)

        # Set the solver sense
        if problem.getSense() == LpMaximization:
            self.CPXchgobjsen(self._env, cplex_model, CPX_MAX)
        elif problem.getSense() == LpMinimization:
            self.CPXchgobjsen(self._env, cplex_model, CPX_MIN)
        else:
            raise RuntimeError("Unknown problem sense :/")

        # Allocate memory for variables
        obj_coeff = np.zeros(num_cols, dtype=np.double)
        var_lb = np.zeros(num_cols, dtype=np.double)
        var_ub = np.zeros(num_cols, dtype=np.double)
        var_type = np.empty(num_cols, dtype='S1')

        # Fill variable data
        for c, var in enumerate(problem.getVars()):
            var_lb[c] = var.getLb()
            var_ub[c] = var.getUb()
            obj_coeff[c] = 0.0
            var_type[c] = b'B' if var.isBinary() else (b'I' if var.isInteger() else b'C')

        # Fill objective coefficients
        for var_unit in problem.getObjectiveFunction().getTerms():
            c = vars_map[var_unit.getVar1().getUuid()]
            obj_coeff[c] = var_unit.getFactor()

        # Add columns to CPLEX
        err = self.CPXnewcols(self._env, cplex_model, num_cols, obj_coeff, var_lb, var_ub, var_type, None)
        if err:
            self.handle_error(err)

        # CSR data allocation
        nnz_count = 0
        start_csr = np.zeros(num_rows + 1, dtype=np.int32)
        index_csr = np.zeros(num_nz, dtype=np.int32)
        value_csr = np.zeros(num_nz, dtype=np.double)

        # Fill in the constraints
        for r, constraint in enumerate(problem.getConstraints()):
            start_csr[r] = nnz_count

            for var_unit in constraint.getVarUnits():
                value_csr[nnz_count] = var_unit.getFactor()
                c = vars_map[var_unit.getVar1().getUuid()]
                index_csr[nnz_count] = c
                nnz_count += 1

            lb, ub = constraint.getLhs(), constraint.getRhs()
            sense = self.get_constraint_sense(lb, ub)
            rhs = lb if sense != b'E' else ub

            # Add rows (constraints)
            err = self.CPXaddrows(self._env, cplex_model, 0, num_rows, nnz_count, rhs, sense, start_csr, index_csr,
                                  value_csr, None, None)
            if err:
                self.handle_error(err)

        # Solve the problem
        if problem.isMip():
            err = self.CPXmipopt(self._env, cplex_model)
        else:
            err = self.CPXlpopt(self._env, cplex_model)
        if err:
            self.handle_error(err)

        # Gather results
        res.setObjective(self.CPXgetobjval(self._env, cplex_model))
        self.CPXgetx(self._env, cplex_model, res.getVarSolutionPtr(), 0, num_cols - 1)
        self.CPXgetslack(self._env, cplex_model, res.getConstraintShadowPtr(), 0, num_rows - 1)

        # Check solution status
        solstat = self.CPXgetstat(self._env, cplex_model)
        self.check_solution_status(solstat, res)

        # Clean up
        err = self.CPXfreeprob(self._env, byref(cplex_model))
        if err:
            self.handle_error(err)

        return res

    def handle_error(self, err):
        """
        Handle CPLEX error
        :param err:
        :return:
        """
        errmsg = ctypes.create_string_buffer(1024)
        self.CPXgeterrorstring(self._env, err, errmsg)
        print(f"Cplex error {err}: {errmsg.value.decode()}")
        raise RuntimeError(f"Cplex error {err}: {errmsg.value.decode()}")

    def get_constraint_sense(self, lb, ub):
        """

        :param lb:
        :param ub:
        :return:
        """
        if lb == ub:
            return b'E'  # Equality constraint
        elif lb <= float('-inf') and ub >= float('inf'):
            return b'R'  # Range constraint (unbounded)
        elif lb <= float('-inf'):
            return b'L'  # Less than or equal constraint
        elif ub >= float('inf'):
            return b'G'  # Greater than or equal constraint
        else:
            raise RuntimeError("Unknown constraint bounds.")

    def check_solution_status(self, solstat, res):
        """

        :param solstat:
        :param res:
        :return:
        """
        if solstat == CPX_STAT_OPTIMAL:
            res.setOptimal(True)
            res.setAcceptable(True)
        elif solstat == CPX_STAT_FEASIBLE:
            res.setOptimal(False)
            res.setAcceptable(True)
        else:
            res.setOptimal(False)
            res.setAcceptable(False)


if __name__ == "__main__":
    # Example usage
    cplex_lib = CplexLib()
    if cplex_lib._is_available:
        print(f"CPLEX Version: {cplex_lib._version}")
    else:
        print("CPLEX library not found or failed to load.")
