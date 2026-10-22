"""Optional third-party installations must not prevent engine startup."""

from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('failure', ('absent', 'ImportError', 'AttributeError', 'OSError',
                                   'RuntimeError', 'ValueError', 'TypeError', 'missing_api',
                                   'missing_dependency'))
def test_broken_optional_dependencies_do_not_break_startup(tmp_path: Path, failure: str) -> None:
    """Import the engine with isolated, deliberately broken third-party modules.

    :param tmp_path: Directory containing substitute packages.
    :param failure: Missing package, missing export, or import failure to reproduce.
    :return: None.
    """
    # Fresh interpreters reproduce startup failures that cached imports would hide.
    # Keep stale APIs and native import failures covered, not only missing packages.
    modules: tuple[str, ...] = (
        'pypsa', 'pandapower', 'pypowsybl', 'power_grid_model', 'gurobi_optimods',
        'ortools', 'cvxopt', 'cvxoptklu', 'pypardiso', 'msgspec', 'lxml', 'requests',
    )
    for module_name in modules:
        source: str
        if failure == 'absent':
            source = f'raise ModuleNotFoundError("{module_name} absent", name={module_name!r})\n'
        elif failure == 'missing_api':
            source = '# Package imports successfully but lacks the API used by VeraGrid.\n'
        elif failure == 'missing_dependency':
            source = 'raise ModuleNotFoundError("transitive dependency absent", name="transitive_dependency")\n'
        else:
            source = f'raise {failure}("incompatible optional installation")\n'
        (tmp_path / f'{module_name}.py').write_text(source)

    source_root: Path = Path(__file__).resolve().parents[1]
    script: str = (
        'import sys\n'
        'from io import BytesIO\n'
        f'sys.path.insert(0, {str(source_root)!r})\n'
        f'sys.path.insert(0, {str(tmp_path)!r})\n'
        'import VeraGridEngine as vg\n'
        'assert vg.PROPERLY_LOADED_API\n'
        'from VeraGridEngine.IO.others import pypsa_parser as pypsa\n'
        'from VeraGridEngine.IO.others import pandapower_parser as panda\n'
        'from VeraGridEngine.IO.iidm import iidm_parser_pypowsybl as iidm\n'
        'from VeraGridEngine.Compilers import circuit_to_pgm as pgm\n'
        'from VeraGridEngine.Compilers import circuit_to_optimods as optimods\n'
        'from VeraGridEngine.Utils.MIP import selected_interface as mip\n'
        'from VeraGridEngine.Utils.NumericalMethods import sparse_solve as sparse\n'
        'from VeraGridEngine.IO.veragrid import zip_interface as archive, remote\n'
        'from VeraGridEngine.IO.cim.cgmes import cgmes_data_parser as xml\n'
        'assert not pypsa.PYPSA_AVAILABLE\n'
        'assert not panda.PANDAPOWER_AVAILABLE\n'
        'assert not iidm.PYPOWSYBL_AVAILABLE\n'
        'assert not pgm.PGM_AVAILABLE\n'
        'assert not optimods.GUROBI_OPTIMODS_AVAILABLE\n'
        'assert not mip.ORTOOLS_AVAILABLE\n'
        'assert not archive._HAS_MSGSPEC\n'
        'assert not remote.REQUESTS_AVAILABLE\n'
        'assert vg.SparseSolver.KLU not in sparse.get_available_sparse_solvers()\n'
        'assert vg.SparseSolver.Pardiso not in sparse.get_available_sparse_solvers()\n'
        'assert vg.SparseSolver.SuperLU in sparse.get_available_sparse_solvers()\n'
        'assert xml.ET.__name__ == "xml.etree.ElementTree"\n'
        'assert archive.load_json_from_file_pointer(BytesIO(b"{\\"value\\": 7}")) == dict(value=7)\n'
        'xml_data = xml.parse_xml_stream_to_dict(BytesIO(\n'
        '    b\'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" \'\n'
        '    b\'xmlns:cim="http://iec.ch/TC57/2013/CIM-schema-cim16#">\'\n'
        '    b\'<cim:Substation rdf:ID="station"><cim:IdentifiedObject.name>Test</cim:IdentifiedObject.name>\'\n'
        '    b\'</cim:Substation></rdf:RDF>\'))\n'
        'assert "Substation" in xml_data\n'
        'logger = vg.Logger()\n'
        'pypsa.parse_pypsa_netcdf("unused.nc", logger)\n'
        'assert pypsa.PYPSA_UNAVAILABLE_REASON in logger.entries[-1].msg\n'
        'parser = panda.Panda2VeraGrid("unused.json", logger)\n'
        'assert parser.panda_net is None\n'
        'assert panda.PANDAPOWER_UNAVAILABLE_REASON in logger.entries[-1].msg\n'
        'open("unused.xiidm", "w").close()\n'
        'iidm.IidmParser("unused.xiidm", logger)\n'
        'assert iidm.PYPOWSYBL_UNAVAILABLE_REASON in logger.entries[-1].msg\n'
        'try:\n'
        '    pgm.to_pgm(vg.MultiCircuit())\n'
        'except ImportError as error:\n'
        '    assert pgm.PGM_UNAVAILABLE_REASON in str(error)\n'
        'else:\n'
        '    raise AssertionError("Unavailable PGM was called")\n'
        'try:\n'
        '    optimods.solve_acopf(dict())\n'
        'except ImportError as error:\n'
        '    assert optimods.GUROBI_OPTIMODS_UNAVAILABLE_REASON in str(error)\n'
        'else:\n'
        '    raise AssertionError("Unavailable Optimods was called")\n'
        'print("optional dependency startup passed")\n'
    )
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, '-c', script], cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'optional dependency startup passed' in result.stdout
    if failure == 'absent':
        assert 'Optional integration disabled' not in result.stderr
    else:
        assert 'Optional integration disabled' in result.stderr


def test_pypsa_missing_format_api_is_reported(tmp_path: Path) -> None:
    """Keep missing reader methods from escaping as an AttributeError.

    :param tmp_path: Isolated package directory.
    :return: None.
    """
    (tmp_path / 'pypsa.py').write_text('class Network:\n    __slots__ = ()\n')
    source_root: Path = Path(__file__).resolve().parents[1]
    script: str = (
        'import sys\n'
        f'sys.path.insert(0, {str(source_root)!r})\n'
        f'sys.path.insert(0, {str(tmp_path)!r})\n'
        'from VeraGridEngine.IO.others import pypsa_parser as parser\n'
        'from VeraGridEngine.basic_structures import Logger\n'
        'assert parser.PYPSA_AVAILABLE\n'
        'logger = Logger()\n'
        'assert parser.parse_pypsa_netcdf("unused.nc", logger).get_bus_number() == 0\n'
        'assert "import_from_netcdf" in logger.entries[-1].msg\n'
        'assert parser.parse_pypsa_hdf5("unused.h5", logger).get_bus_number() == 0\n'
        'assert "import_from_hdf5" in logger.entries[-1].msg\n'
    )
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, '-c', script], cwd=tmp_path, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_installed_pandapower_still_imports_projects(tmp_path: Path) -> None:
    """Round-trip a real network through the optional JSON reader when installed.

    :param tmp_path: Temporary project directory.
    :return: None.
    """
    from VeraGridEngine.IO.others.pandapower_parser import PANDAPOWER_AVAILABLE, Panda2VeraGrid
    from VeraGridEngine.Devices.multi_circuit import MultiCircuit

    if PANDAPOWER_AVAILABLE:
        import pandapower as pp

        network: pp.pandapowerNet = pp.create_empty_network(f_hz=60.0)
        bus_index: int = pp.create_bus(network, vn_kv=110.0, name='Test bus')
        pp.create_ext_grid(network, bus_index)
        pp.create_load(network, bus_index, p_mw=5.0, q_mvar=1.0)
        file_name: str = str(tmp_path / 'network.json')
        pp.to_json(network, file_name)

        parser: Panda2VeraGrid = Panda2VeraGrid(file_name)
        grid: MultiCircuit = parser.get_multicircuit()
        assert grid.get_bus_number() == 1
        assert grid.get_loads_number() == 1
        assert grid.fBase == 60.0
        assert grid.loads[0].P == 5.0
    else:
        pytest.skip('pandapower integration is unavailable')
