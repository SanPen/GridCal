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
# Users would need to install HiGHS on their machine and provide the path to the executable. Please look at this thread: https://github.com/ERGO-Code/HiGHS/issues/527#issuecomment-894852288
# More instructions on: https://www.highs.dev
from __future__ import annotations
import os
from typing import List, TYPE_CHECKING
import GridCalEngine.Utils.ThirdParty.pulp.constants as constants
from GridCalEngine.Utils.ThirdParty.pulp.apis.lp_solver_cmd import LpSolver_CMD, subprocess

if TYPE_CHECKING:
    from GridCalEngine.Utils.ThirdParty.pulp.model.lp_problem import LpProblem


class HiGHS_CMD(LpSolver_CMD):
    """The HiGHS_CMD solver"""

    name: str = "HiGHS_CMD"

    SOLUTION_STYLE: int = 0

    def __init__(self,
                 path: None | str = None,
                 keepFiles: bool = False,
                 mip: bool = True,
                 msg: bool = True,
                 options: None | List = None,
                 timeLimit: None | float = None,
                 gapRel: None | float = None,
                 gapAbs: None | float = None,
                 threads: None | int = None,
                 logPath: None | str = None,
                 warmStart: bool = False) -> None:
        """
        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param float timeLimit: maximum time for solver (in seconds)
        :param float gapRel: relative gap tolerance for the solver to stop (in fraction)
        :param float gapAbs: absolute gap tolerance for the solver to stop
        :param list[str] options: list of additional options to pass to solver
        :param bool keepFiles: if True, files are saved in the current directory and not deleted after solving
        :param str path: path to the solver binary (you can get binaries for your platform from https://github.com/JuliaBinaryWrappers/HiGHS_jll.jl/releases, or else compile from source - https://highs.dev)
        :param int threads: sets the maximum number of threads
        :param str logPath: path to the log file
        :param bool warmStart: if True, the solver will use the current value of variables as a start
        """
        LpSolver_CMD.__init__(
            self,
            mip=mip,
            msg=msg,
            timeLimit=timeLimit,
            gapRel=gapRel,
            gapAbs=gapAbs,
            options=options,
            path=path,
            keepFiles=keepFiles,
            threads=threads,
            logPath=logPath,
            warmStart=warmStart,
        )

    def defaultPath(self) -> str:
        """

        :return:
        """
        return self.executableExtension("highs")

    def available(self) -> str | None:
        """
        Path to the solver, otherwise None if the solver is available
        """
        return self.executable(self.path)

    def actualSolve(self, lp: LpProblem):
        """
        Solve a well formulated lp problem
        :param lp:
        :return:
        """

        if not self.executable(self.path):
            raise constants.PulpSolverError("PuLP: cannot execute " + self.path)
        lp.checkDuplicateVars()

        tmpMps, tmpSol, tmpOptions, tmpLog, tmpMst = self.create_tmp_files(
            lp.name, "mps", "sol", "HiGHS", "HiGHS_log", "mst"
        )
        lp.writeMPS(tmpMps, with_objsense=True)

        file_options: List[str] = list()
        file_options.append(f"solution_file={tmpSol}")
        file_options.append("write_solution_to_file=true")
        file_options.append(f"write_solution_style={HiGHS_CMD.SOLUTION_STYLE}")
        if not self.msg:
            file_options.append("log_to_console=false")
        if "threads" in self.optionsDict:
            file_options.append(f"threads={self.optionsDict['threads']}")
        if "gapRel" in self.optionsDict:
            file_options.append(f"mip_rel_gap={self.optionsDict['gapRel']}")
        if "gapAbs" in self.optionsDict:
            file_options.append(f"mip_abs_gap={self.optionsDict['gapAbs']}")
        if "logPath" in self.optionsDict:
            highs_log_file = self.optionsDict["logPath"]
        else:
            highs_log_file = tmpLog
        file_options.append(f"log_file={highs_log_file}")

        command: List[str] = list()
        command.append(self.path)
        command.append(tmpMps)
        command.append(f"--options_file={tmpOptions}")
        if self.timeLimit is not None:
            command.append(f"--time_limit={self.timeLimit}")
        if not self.mip:
            command.append("--solver=simplex")
        if "threads" in self.optionsDict:
            command.append("--parallel=on")
        if self.optionsDict.get("warmStart", False):
            self.writesol(tmpMst, lp)
            command.append(f"--read_solution_file={tmpMst}")

        options = iter(self.options)
        for option in options:
            # assumption: all cli and file options require an argument which is provided after the equal sign (=)
            if "=" not in option:
                option += f"={next(options)}"

            # identify cli options by a leading dash (-) and treat other options as file options
            if option.startswith("-"):
                command.append(option)
            else:
                file_options.append(option)

        with open(tmpOptions, "w") as options_file:
            options_file.write("\n".join(file_options))
        # print(command)
        process = subprocess.Popen(command, stdout=None, stderr=None)

        # HiGHS return code semantics (see: https://github.com/ERGO-Code/HiGHS/issues/527#issuecomment-946575028)
        # - -1: error
        # -  0: success
        # -  1: warning
        # process = subprocess.run(command, stdout=sys.stdout, stderr=sys.stderr)
        if process.wait() == -1:
            raise constants.PulpSolverError(
                "Pulp: Error while executing HiGHS, use msg=True for more details"
                + self.path
            )

        with open(highs_log_file, "r") as log_file:
            lines = log_file.readlines()
        lines = [line.strip().split() for line in lines]

        # LP
        model_line = [line for line in lines if line[:2] == ["Model", "status"]]
        if len(model_line) > 0:
            model_status = " ".join(model_line[0][3:])  # Model status: ...
        else:
            # ILP
            model_lines = [line for line in lines if "Status" in line]
            if len(model_lines) > 0:
                model_line = model_lines[0]
                model_status = " ".join(model_line[1:])
            else:
                model_status = ""
        sol_line = [line for line in lines if line[:2] == ["Solution", "status"]]
        sol_line = sol_line[0] if len(sol_line) > 0 else ["Not solved"]
        sol_status = sol_line[-1]
        if model_status.lower() == "optimal":  # optimal
            status, status_sol = (
                constants.LpStatusOptimal,
                constants.LpSolutionOptimal,
            )
        elif sol_status.lower() == "feasible":  # feasible
            # Following the PuLP convention
            status, status_sol = (
                constants.LpStatusOptimal,
                constants.LpSolutionIntegerFeasible,
            )
        elif model_status.lower() == "infeasible":  # infeasible
            status, status_sol = (
                constants.LpStatusInfeasible,
                constants.LpSolutionInfeasible,
            )
        elif model_status.lower() == "unbounded":  # unbounded
            status, status_sol = (
                constants.LpStatusUnbounded,
                constants.LpSolutionUnbounded,
            )
        else:  # no solution
            status, status_sol = (
                constants.LpStatusNotSolved,
                constants.LpSolutionNoSolutionFound,
            )

        if not os.path.exists(tmpSol) or os.stat(tmpSol).st_size == 0:
            status_sol = constants.LpSolutionNoSolutionFound
            values = None
        elif status_sol in {
            constants.LpSolutionNoSolutionFound,
            constants.LpSolutionInfeasible,
            constants.LpSolutionUnbounded,
        }:
            values = None
        else:
            values = self.readsol(tmpSol)

        self.delete_tmp_files(tmpMps, tmpSol, tmpOptions, tmpLog, tmpMst)
        lp.assignStatus(status, status_sol)

        if status == constants.LpStatusOptimal:
            lp.assignVarsVals(values)

        return status

    @staticmethod
    def writesol(filename: str, lp: LpProblem):
        """Writes a HiGHS solution file"""

        variable_rows = []
        for var in lp.variables():  # zero variables must be included
            variable_rows.append(f"{var.name} {var.varValue or 0}")

        # Required preamble for HiGHS to accept a solution
        all_rows = [
            "Model status",
            "None",
            "",
            "# Primal solution values",
            "Feasible",
            "",
            f"# Columns {len(variable_rows)}",
        ]
        all_rows.extend(variable_rows)

        with open(filename, "w") as file:
            file.write("\n".join(all_rows))

    @staticmethod
    def readsol(filename: str):
        """Read a HiGHS solution file"""
        with open(filename) as file:
            lines = file.readlines()

        begin, end = None, None
        for index, line in enumerate(lines):
            if begin is None and line.startswith("# Columns"):
                begin = index + 1
            if end is None and line.startswith("# Rows"):
                end = index
        if begin is None or end is None:
            raise constants.PulpSolverError("Cannot read HiGHS solver output")

        values = {}
        for line in lines[begin:end]:
            name, value = line.split()
            values[name] = float(value)
        return values

