import numpy as np
import pandas as pd
from GridCalEngine.Simulations.results_template import ResultsTemplate
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.enumerations import StudyResultsType, ResultTypes, DeviceType
from GridCalEngine.basic_structures import StrVec, Vec


class SCOPFResults(ResultsTemplate):
    def __init__(self,
                 bus_names: StrVec,
                 generator_names: StrVec,
                 branch_names: StrVec,
                 Pg: np.ndarray,
                 contingency_outputs: list,
                 converged: bool):
        super().__init__(
            name='SCOPF',
            available_results={
                ResultTypes.GeneratorResults: [ResultTypes.GeneratorPower],
                ResultTypes.ReportsResults: [ResultTypes.ContingencyFlowsReport]
            },
            time_array=None,
            clustering_results=None,
            study_results_type=StudyResultsType.SecurityConstrainedOptimalPowerFlow
        )

        self.bus_names = bus_names
        self.generator_names = generator_names
        self.branch_names = branch_names
        self.Pg = Pg
        self.contingency_outputs = contingency_outputs
        self.converged = converged

        # Register for serialization/viewing
        self.register(name='bus_names', tpe=StrVec)
        self.register(name='generator_names', tpe=StrVec)
        self.register(name='branch_names', tpe=StrVec)
        self.register(name='Pg', tpe=Vec)
        self.register(name='converged', tpe=bool)
        self.register(name='contingency_outputs', tpe=list)

    def get_generator_df(self) -> pd.DataFrame:
        return pd.DataFrame(data={'P': self.Pg}, index=self.generator_names)

    def get_contingency_df(self) -> pd.DataFrame:
        records = []
        for output in self.contingency_outputs:
            records.append({
                'Contingency Index': output.get("contingency_index", -1),
                'W_k': output.get("W_k", 0.0),
                'Z_k (sum)': np.sum(output.get("Z_k", [])),
                'u_j (sum)': np.sum(output.get("u_j", [])),
                'Active Branches': np.sum(output.get("active", [])),
            })
        return pd.DataFrame(records)

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

        elif result_type == ResultTypes.ContingencyFlowsReport:
            df = self.get_contingency_df()
            return ResultsTable(
                data=df.values,
                index=df.index,
                idx_device_type=DeviceType.NoDevice,
                columns=list(df.columns),
                cols_device_type=DeviceType.NoDevice,
                title="Contingency Outputs"
            )

        else:
            raise Exception("Result type not supported in SCOPFResults: " + str(result_type))
