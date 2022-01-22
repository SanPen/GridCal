# PuLP : Python LP Modeler
# Version 2.4

# Copyright (c) 2002-2005, Jean-Sebastien Roy (js@jeannot.org)
# Modifications Copyright (c) 2007- Stuart Anthony Mitchell (s.mitchell@auckland.ac.nz)
# $Id:solvers.py 1791 2008-04-23 22:54:34Z smit023 $

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""

# Modified by Sam Mathew (@samiit on Github)
# Users would need to install HiGHS on their machine and provide the path to the executable.
# Please look at this thread: https://github.com/ERGO-Code/HiGHS/issues/527#issuecomment-894852288
# More instructions on: https://www.highs.dev
import os
import sys
import warnings
from GridCal.ThirdParty.pulp.solvers import *
from GridCal.ThirdParty.pulp import constants


class HiGHS_CMD(LpSolver_CMD):
    """The HiGHS_CMD solver"""

    name = "HiGHS_CMD"

    def __init__(
        self,
        path=None,
        keepFiles=False,
        mip=True,
        msg=True,
        options=[],
    ):
        """
        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param list options: list of additional options to pass to solver
        :param bool keepFiles: if True, files are saved in the current directory and not deleted after solving
        :param str path: path to the solver binary (you can get binaries for your platform from https://github.com/JuliaBinaryWrappers/HiGHS_jll.jl/releases, or else compile from source - https://highs.dev)
        """
        LpSolver_CMD.__init__(
            self,
            mip=mip,
            msg=msg,
            options=options,
            path=path,
            keepFiles=keepFiles,
        )

    def defaultPath(self):
        return self.executableExtension("highs")

    def available(self):
        """True if the solver is available"""
        return self.executable(self.path)

    def actualSolve(self, lp):
        """
        Solve a well formulated lp problem
        """

        if not self.executable(self.path):
            raise PulpSolverError("PuLP: cannot execute " + self.path)

        tmp_mps, tmp_sol, tmp_options, tmp_log = self.create_tmp_files(lp.name, "mps", "sol", "HiGHS", "HiGHS_log")

        # https://www.maths.ed.ac.uk/hall/HiGHS/HighsOptions.html
        write_lines = [
            "solution_file = %s\n" % tmp_sol,
            "write_solution_to_file = true\n",
            'parallel = "on"\n',
            # 'threads="on"\n'
            'threads={0}\n'.format(os.cpu_count()),  # max number of threads
        ]
        with open(tmp_options, "w") as fp:
            fp.writelines(write_lines)

        if lp.sense == constants.LpMaximize:
            # we swap the objectives
            # because it does not handle maximization.
            warnings.warn(
                "HiGHS_CMD does not currently allow maximization, "
                "we will minimize the inverse of the objective function."
            )
            lp += -lp.objective
        lp.checkDuplicateVars()
        lp.checkLengthVars(52)
        lp.writeMPS(tmp_mps)  # , mpsSense=constants.LpMinimize)

        # just to report duplicated variables:
        try:
            os.remove(tmp_sol)
        except:
            pass

        cmd = self.path
        cmd += " %s" % tmp_mps
        cmd += " --options_file %s" % tmp_options

        for option in self.options:
            cmd += " " + option

        if lp.isMIP():
            if not self.mip:
                warnings.warn("HiGHS_CMD cannot solve the relaxation of a problem")

        if self.msg:
            pipe = None
        else:
            pipe = open(os.devnull, "w")

        lp_status = None

        with subprocess.Popen(
            cmd.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        ) as proc, open(tmp_log, "w") as log_file:
            for line in proc.stdout:
                if self.msg:
                    sys.__stdout__.write(line)
                log_file.write(line)

        # We need to undo the objective swap before finishing
        if lp.sense == constants.LpMaximize:
            lp += -lp.objective

        # The return code for HiGHS on command line follows:
        # 0:program ran successfully,
        # 1: warning,
        # -1: error
        # see https://github.com/ERGO-Code/HiGHS/issues/527#issuecomment-946575028
        return_code = proc.wait()

        if return_code in [0, 1]:
            with open(tmp_log, "r") as log_file:
                content = log_file.readlines()
            content = [l.strip().split() for l in content]

            # LP
            model_line = [l for l in content if l[:2] == ["Model", "status"]]
            if len(model_line) > 0:
                model_status = " ".join(model_line[0][3:])  # Model status: ...
            else:
                # ILP
                model_line = [l for l in content if "Status" in l][0]
                model_status = " ".join(model_line[1:])

            sol_line = [l for l in content if l[:2] == ["Solution", "status"]]
            sol_line = sol_line[0] if len(sol_line) > 0 else ["Not solved"]
            sol_status = sol_line[-1]

            if model_status.lower() == "optimal":  # optimal
                status, status_sol = (constants.LpStatusOptimal, constants.LpSolutionOptimal)

            elif sol_status.lower() == "feasible":  # feasible
                # Following the PuLP convention
                status, status_sol = (
                    constants.LpStatusOptimal,
                    constants.LpSolutionIntegerFeasible,
                )
            elif model_status.lower() == "infeasible":  # infeasible
                status, status_sol = (
                    constants.LpStatusInfeasible,
                    constants.LpSolutionNoSolutionFound,
                )
            elif model_status.lower() == "unbounded":  # unbounded
                status, status_sol = (
                    constants.LpStatusUnbounded,
                    constants.LpSolutionNoSolutionFound,
                )
        else:
            status = constants.LpStatusUndefined
            status_sol = constants.LpSolutionNoSolutionFound
            # raise PulpSolverError("Pulp: Error while executing", self.path)

        if status == constants.LpStatusUndefined:
            raise PulpSolverError("Pulp: Error while executing", self.path)

        if not os.path.exists(tmp_sol) or os.stat(tmp_sol).st_size == 0:
            status_sol = constants.LpSolutionNoSolutionFound
            values = None
        else:
            values, shadowPrices = self.readsol(lp.variables(), tmp_sol)

        self.delete_tmp_files(tmp_mps, tmp_sol, tmp_options, tmp_log)
        lp.assignStatus(status, status_sol)

        if status != LpStatusInfeasible:
            lp.assignVarsVals(values)
            lp.assignConsPi(shadowPrices)
        return status

    @staticmethod
    def readsol(variables, filename):
        """Read a HiGHS solution file"""
        with open(filename) as f:
            content = f.readlines()
        content = [l.strip() for l in content]
        values = dict()
        shadow_prices = dict()

        if not len(content):  # if file is empty, update the status_sol
            return None

        def search_first(arr, txt):
            for i, val in enumerate(arr):
                if len(val) > 0:
                    if val[0] == '#':
                        if txt in val:
                            return i
            return None

        # extract everything between the line Columns and Rows
        i1 = search_first(content, "Columns")
        i2 = search_first(content, "Rows")
        solution = content[i1 + 1: i2]

        # check whether it is an LP or an ILP
        if "# Basis" in content:  # LP
            for var, line in zip(variables, solution):
                value = line.split()[1]
                values[var.name] = float(value)
        else:  # ILP
            for var, value in zip(variables, solution):
                values[var.name] = float(value)

        # fill shadow prices
        i3 = search_first(content, "Dual solution")
        dual_content = content[i3:]
        i1 = search_first(dual_content, "Rows")
        i2 = search_first(dual_content, "Basis")
        # dual_solution = dual_content[i1 + 1: i2]
        dual_shadow = dual_content[i1 + 1: i2]
        for x in dual_shadow:
            l = x.split(" ")
            if len(l) == 2:
                shadow_prices[l[0]] = float(l[1])

        return values, shadow_prices
