import numpy as np
import pandas as pd
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, DeviceType
from GridCalEngine.basic_structures import StrVec, Vec


class SCOPFNNResults(ResultsTemplate):
    def __init__(self,
                 bus_names: StrVec,
                 generator_names: StrVec,
                 branch_names: StrVec,
                 Pg: np.ndarray):
        super().__init__(
            name='SCOPF_NN',
            available_results={
                ResultTypes.GeneratorResults: [ResultTypes.GeneratorPower]
            },
            time_array=None,
            clustering_results=None,
            study_results_type=StudyResultsType.SecurityConstrainedOptimalPowerFlow
        )

        self.bus_names = bus_names
        self.generator_names = generator_names
        self.branch_names = branch_names
        self.Pg = Pg

        # Register for serialization/viewing
        self.register(name='bus_names', tpe=StrVec)
        self.register(name='generator_names', tpe=StrVec)
        self.register(name='branch_names', tpe=StrVec)
        self.register(name='Pg', tpe=Vec)

    def get_generator_df(self) -> pd.DataFrame:
        return pd.DataFrame(data={'P': self.Pg}, index=self.generator_names)

    def mdl(self, result_type) -> ResultsTable:
        if result_type == ResultTypes.GeneratorPower:
            return ResultsTable(
                data=self.Pg,
                index=self.generator_names,
                idx_device_type=DeviceType.GeneratorDevice,
                columns=[result_type.value],
                cols_device_type=DeviceType.NoDevice,
                title="Generator Active Power",
                ylabel="(MW)",
                xlabel="",
                units="(MW)"
            )
        else:
            raise Exception("Result type not supported in SCOPFNNResults: " + str(result_type))
