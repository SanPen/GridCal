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

"""
This file contains the solver classes for PuLP
Note that the solvers that require a compiled extension may not work in
the current version
"""
from __future__ import annotations
import os
import platform
import shutil
import sys
import ctypes
import subprocess
from uuid import uuid4
import configparser
from typing import Union, Tuple, List
from GridCalEngine.Utils.ThirdParty.pulp.apis.lp_solver import LpSolver


Parser = configparser.ConfigParser
devnull = subprocess.DEVNULL


# import configuration information
def initialize(filename: str,
               operating_system: str = "linux",
               arch: str = "64") -> Tuple[str, str, int, List[str], str, str, str, str, str, str]:
    """
    reads the configuration file to initialise the module
    :param filename:
    :param operating_system:
    :param arch:
    :return:
    """
    here = os.path.dirname(filename)
    config = Parser({"here": here, "os": operating_system, "arch": arch})
    config.read(filename)

    try:
        cplex_dll_path = config.get("locations", "CplexPath")
    except configparser.Error:
        cplex_dll_path = "libcplex110.so"
    try:
        try:
            ilm_cplex_license = (
                config.get("licenses", "ilm_cplex_license")
                .decode("string-escape")
                .replace('"', "")
            )
        except AttributeError:
            ilm_cplex_license = config.get("licenses", "ilm_cplex_license").replace(
                '"', ""
            )
    except configparser.Error:
        ilm_cplex_license = ""
    try:
        ilm_cplex_license_signature = config.getint(
            "licenses", "ilm_cplex_license_signature"
        )
    except configparser.Error:
        ilm_cplex_license_signature = 0
    try:
        coinMP_path = config.get("locations", "CoinMPPath").split(", ")
    except configparser.Error:
        coinMP_path = ["libCoinMP.so"]
    try:
        gurobi_path = config.get("locations", "GurobiPath")
    except configparser.Error:
        gurobi_path = "/opt/gurobi201/linux32/lib/python2.5"
    try:
        cbc_path = config.get("locations", "CbcPath")
    except configparser.Error:
        cbc_path = "cbc"
    try:
        glpk_path = config.get("locations", "GlpkPath")
    except configparser.Error:
        glpk_path = "glpsol"
    try:
        pulp_cbc_path = config.get("locations", "PulpCbcPath")
    except configparser.Error:
        pulp_cbc_path = "cbc"
    try:
        scip_path = config.get("locations", "ScipPath")
    except configparser.Error:
        scip_path = "scip"
    try:
        fscip_path = config.get("locations", "FscipPath")
    except configparser.Error:
        fscip_path = "fscip"
    for i, path in enumerate(coinMP_path):
        if not os.path.dirname(path):
            # if no pathname is supplied assume the file is in the same directory
            coinMP_path[i] = os.path.join(os.path.dirname(config_filename), path)
    return (
        cplex_dll_path,
        ilm_cplex_license,
        ilm_cplex_license_signature,
        coinMP_path,
        gurobi_path,
        cbc_path,
        glpk_path,
        pulp_cbc_path,
        scip_path,
        fscip_path,
    )


# pick up the correct config file depending on operating system
PULPCFGFILE = "pulp.cfg"
is_64bits = sys.maxsize > 2 ** 32
if is_64bits:
    arch = "64"
    if platform.machine().lower() in ["aarch64", "arm64"]:
        arch = "arm64"
else:
    arch = "32"
operating_system = None
if sys.platform in ["win32", "cli"]:
    operating_system = "win"
    PULPCFGFILE += ".win"
elif sys.platform in ["darwin"]:
    operating_system = "osx"
    PULPCFGFILE += ".osx"
else:
    operating_system = "linux"
    PULPCFGFILE += ".linux"

DIRNAME = os.path.dirname(__file__)
config_filename = os.path.normpath(os.path.join(DIRNAME, "..", PULPCFGFILE))

(
    cplex_dll_path,
    ilm_cplex_license,
    ilm_cplex_license_signature,
    coinMP_path,
    gurobi_path,
    cbc_path,
    glpk_path,
    pulp_cbc_path,
    scip_path,
    fscip_path,
) = initialize(config_filename, operating_system, arch)


class LpSolver_CMD(LpSolver):
    """A generic command line LP Solver"""

    name = "LpSolver_CMD"

    def __init__(self, path=None, keepFiles=False, *args, **kwargs):
        """

        :param bool mip: if False, assume LP even if integer variables
        :param bool msg: if False, no log is shown
        :param list options: list of additional options to pass to solver (format depends on the solver)
        :param float timeLimit: maximum time for solver (in seconds)
        :param str path: a path to the solver binary
        :param bool keepFiles: if True, files are saved in the current directory and not deleted after solving
        :param args: parameters to pass to :py:class:`LpSolver`
        :param kwargs: parameters to pass to :py:class:`LpSolver`
        """
        LpSolver.__init__(self, *args, **kwargs)
        if path is None:
            self.path = self.defaultPath()
        else:
            self.path = path
        self.keepFiles = keepFiles
        self.tmpDir = ""
        self.setTmpDir()

    def copy(self):
        """Make a copy of self"""

        aCopy = LpSolver.copy(self)
        aCopy.path = self.path
        aCopy.keepFiles = self.keepFiles
        aCopy.tmpDir = self.tmpDir
        return aCopy

    def setTmpDir(self):
        """Set the tmpDir attribute to a reasonnable location for a temporary
        directory"""
        if os.name != "nt":
            # On unix use /tmp by default
            self.tmpDir = os.environ.get("TMPDIR", "/tmp")
            self.tmpDir = os.environ.get("TMP", self.tmpDir)
        else:
            # On Windows use the current directory
            self.tmpDir = os.environ.get("TMPDIR", "")
            self.tmpDir = os.environ.get("TMP", self.tmpDir)
            self.tmpDir = os.environ.get("TEMP", self.tmpDir)
        if not os.path.isdir(self.tmpDir):
            self.tmpDir = ""
        elif not os.access(self.tmpDir, os.F_OK + os.W_OK):
            self.tmpDir = ""

    def create_tmp_files(self, name, *args):
        """

        :param name:
        :param args:
        :return:
        """
        if self.keepFiles:
            prefix = name
        else:
            prefix = os.path.join(self.tmpDir, uuid4().hex)
        return (f"{prefix}-pulp.{n}" for n in args)

    def silent_remove(self, file: Union[str, bytes, os.PathLike]) -> None:
        """

        :param file:
        """
        try:
            os.remove(file)
        except FileNotFoundError:
            pass

    def delete_tmp_files(self, *args):
        """

        :param args:
        :return:
        """
        if self.keepFiles:
            return
        for file in args:
            self.silent_remove(file)

    def defaultPath(self) -> str:
        """
        Get the default path
        """
        raise NotImplementedError

    @staticmethod
    def executableExtension(name):
        """

        :param name:
        :return:
        """
        if os.name != "nt":
            return name
        else:
            return name + ".exe"

    @staticmethod
    def executable(command) -> str:
        """Checks that the solver command is executable,
        And returns the actual path to it."""
        return shutil.which(command)


def ctypesArrayFill(myList, tpe=ctypes.c_double):
    """
    Creates a c array with ctypes from a python list
    type is the type of the c array
    """
    ctype = tpe * len(myList)
    cList = ctype()
    for i, elem in enumerate(myList):
        cList[i] = elem
    return cList
