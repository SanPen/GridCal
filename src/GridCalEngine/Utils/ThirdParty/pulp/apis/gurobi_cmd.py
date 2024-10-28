# PuLP : Python LP Modeler
# Version 1.4.2

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
from __future__ import annotations
from typing import TYPE_CHECKING
import os
import warnings
import GridCalEngine.Utils.ThirdParty.pulp.constants as constants
from GridCalEngine.Utils.ThirdParty.pulp.apis.lp_solver_cmd import LpSolver_CMD, subprocess
from GridCalEngine.Utils.ThirdParty.pulp.paths import get_solvers_config

if TYPE_CHECKING:
    from GridCalEngine.Utils.ThirdParty.pulp.model.lp_problem import LpProblem


class GUROBI_CMD(LpSolver_CMD):
    """
    The GUROBI_CMD solver
    """

    name = "GUROBI_CMD"

    def __init__(self,
                 mip=True,
                 msg=True,
                 timeLimit=None,
                 gapRel=None,
                 gapAbs=None,
                 options=None,
                 warmStart=False,
                 keepFiles=False,
                 path=None,
                 threads=None,
                 logPath=None,
                 mip_start=False):
        """
        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param float timeLimit: maximum time for solver (in seconds)
        :param float gapRel: relative gap tolerance for the solver to stop (in fraction)
        :param float gapAbs: absolute gap tolerance for the solver to stop
        :param int threads: sets the maximum number of threads
        :param list options: list of additional options to pass to solver
        :param bool warmStart: if True, the solver will use the current value of variables as a start
        :param bool keepFiles: if True, files are saved in the current directory and not deleted after solving
        :param str path: path to the solver binary
        :param str logPath: path to the log file
        """
        LpSolver_CMD.__init__(
            self,
            gapRel=gapRel,
            mip=mip,
            msg=msg,
            timeLimit=timeLimit,
            options=options,
            warmStart=warmStart,
            path=path,
            keepFiles=keepFiles,
            threads=threads,
            gapAbs=gapAbs,
            logPath=logPath,
        )

    def defaultPath(self) -> str:
        """

        :return:
        """
        # try to get the executable path from the json config file in the .GridCal folder
        data = get_solvers_config()

        bin_path = data.get('gurobi_bin', None)

        if bin_path is None:
            return self.executableExtension("gurobi_cl")
        else:
            if os.path.exists(bin_path):
                return bin_path
            else:
                return self.executableExtension("gurobi_cl")

    def available(self):
        """True if the solver is available"""
        if not self.executable(self.path):
            return False
        # we execute gurobi once to check the return code.
        # this is to test that the license is active
        result = subprocess.Popen(
            self.path, stdout=subprocess.PIPE, universal_newlines=True
        )
        out, err = result.communicate()
        if result.returncode == 0:
            # normal execution
            return True
        # error: we display the gurobi message
        if self.msg:
            warnings.warn(f"GUROBI error: {out}.")
        return False

    def actualSolve(self, lp: LpProblem):
        """Solve a well formulated lp problem"""

        if not self.executable(self.path):
            raise constants.PulpSolverError("PuLP: cannot execute " + self.path)
        tmpLp, tmpSol, tmpMst = self.create_tmp_files(lp.name, "lp", "sol", "mst")
        vs = lp.writeLP(tmpLp, writeSOS=1)
        try:
            os.remove(tmpSol)
        except:
            pass
        cmd = self.path
        options = self.options + self.getOptions()
        if self.timeLimit is not None:
            options.append(("TimeLimit", self.timeLimit))
        cmd += " " + " ".join([f"{key}={value}" for key, value in options])
        cmd += f" ResultFile={tmpSol}"
        if self.optionsDict.get("warmStart", False):
            self.writesol(filename=tmpMst, vs=vs)
            cmd += f" InputFile={tmpMst}"

        if lp.isMIP():
            if not self.mip:
                warnings.warn("GUROBI_CMD does not allow a problem to be relaxed")
        cmd += f" {tmpLp}"
        if self.msg:
            pipe = None
        else:
            pipe = open(os.devnull, "w")

        return_code = subprocess.call(cmd.split(), stdout=pipe, stderr=pipe)

        # Close the pipe now if we used it.
        if pipe is not None:
            pipe.close()

        if return_code != 0:
            raise constants.PulpSolverError("PuLP: Error while trying to execute " + self.path)

        if not os.path.exists(tmpSol):
            # TODO: the status should be infeasible here, I think
            status = constants.LpStatusNotSolved
            values = reducedCosts = shadowPrices = slacks = None
        else:
            # TODO: the status should be infeasible here, I think
            status, values, reducedCosts, shadowPrices, slacks = self.readsol(tmpSol)
        self.delete_tmp_files(tmpLp, tmpMst, tmpSol, "gurobi.log")
        if status != constants.LpStatusInfeasible:
            lp.assignVarsVals(values)
            lp.assignVarsDj(reducedCosts)
            lp.assignConsPi(shadowPrices)
            lp.assignConsSlack(slacks)
        lp.assignStatus(status)
        return status

    def readsol(self, filename):
        """Read a Gurobi solution file"""
        with open(filename) as my_file:
            try:
                next(my_file)  # skip the objective value
            except StopIteration:
                # Empty file not solved
                status = constants.LpStatusNotSolved
                return status, {}, {}, {}, {}
            # We have no idea what the status is assume optimal
            # TODO: check status for Integer Feasible
            status = constants.LpStatusOptimal

            shadowPrices = {}
            slacks = {}
            shadowPrices = {}
            slacks = {}
            values = {}
            reducedCosts = {}
            for line in my_file:
                if line[0] != "#":  # skip comments
                    name, value = line.split()
                    values[name] = float(value)
        return status, values, reducedCosts, shadowPrices, slacks

    def writesol(self, filename, vs):
        """Writes a GUROBI solution file"""

        values = [(v.name, v.value()) for v in vs if v.value() is not None]
        rows = []
        for name, value in values:
            rows.append(f"{name} {value}")
        with open(filename, "w") as f:
            f.write("\n".join(rows))
        return True

    def getOptions(self):
        # GUROBI parameters: http://www.gurobi.com/documentation/7.5/refman/parameters.html#sec:Parameters
        params_eq = dict(
            logPath="LogFile",
            gapRel="MIPGap",
            gapAbs="MIPGapAbs",
            threads="Threads",
        )
        return [
            (v, self.optionsDict[k])
            for k, v in params_eq.items()
            if k in self.optionsDict and self.optionsDict[k] is not None
        ]
