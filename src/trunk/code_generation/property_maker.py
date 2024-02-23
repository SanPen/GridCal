lst = [
    "k_pf_tau",
    "k_qf_m",
    "k_zero_beq",
    "k_vf_beq",
    "k_vt_m",
    "k_qt_m",
    "k_pf_dp",
    "k_m",
    "k_tau",
    "k_mtau",
    "i_m",
    "i_tau",
    "i_mtau",
    "iPfdp_va",
    "i_vsc",
    "i_vf_beq",
    "i_vt_m",
]

with open("props.py", "w") as props_file:
    for name in lst:
        code = f'''
        @property
            def {name}(self):
                """
                Get {name}
                :return:
                """
                if self.simulation_indices_ is None:
                    self.simulation_indices_ = self.get_simulation_indices()
        
                return self.simulation_indices_.{name}
        '''

        props_file.write(code + "\n")
