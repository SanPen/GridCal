# SPDX-License-Identifier: MPL-2.0
"""Reviewed numeric machine/controller CON orders, ModelLibrary 35.2 data sheets.

These layouts use BUS, quoted MODEL, ID followed by CONs; models with ICON or
remote-signal headers need their own grammar and must not be inferred here.
"""


def standard_dyr_parameters(model: str) -> tuple[str, ...] | None:
    """Look up explicit PSS/E constant order, independently of template parameter order.

    :param model: PSS/E model name.
    :return: Named CON layout, or None for a model needing another reviewed schema.
    """
    layouts: dict[str, tuple[str, ...]] = dict(
        GENTRA=('Tdo1', 'H', 'D', 'Xd', 'Xq', 'Xd1', 'S10', 'S12', 'AF'),
        GENSAE=('Tdo1', 'Tdo2', 'Tqo2', 'H', 'D', 'Xd', 'Xq', 'Xd1', 'Xd2', 'Xl', 'S10', 'S12'),
        GENROE=('Tdo1', 'Tdo2', 'Tqo1', 'Tqo2', 'H', 'D', 'Xd', 'Xq', 'Xd1', 'Xq1', 'Xd2', 'Xl', 'S10', 'S12'),
        SCRX=('TATB', 'TB', 'K', 'TE', 'EMIN', 'EMAX', 'CSWITCH', 'RC_RFD'),
        TGOV1=('R', 'T1', 'VMAX', 'VMIN', 'T2', 'T3', 'Dt'),
        DEGOV=('T1','T2','T3','K','T4','T5','T6','TD','TMAX','TMIN'),
        GAST=('R', 'T1', 'T2', 'T3', 'AT', 'KT', 'VMAX', 'VMIN', 'Dturb'),
        IEESGO=('T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'K1', 'K2', 'K3', 'PMAX', 'PMIN'),
        IEEEG2=('K', 'T1', 'T2', 'T3', 'PMAX', 'PMIN', 'T4'),
        IVOGO=('K1','A1','A2','T1','T2','MAX1','MIN1','K3','A3','A4','T3','T4','MAX3','MIN3','K5','A5','A6','T5','T6','MAX5','MIN5'),
        IVOST=('K1','A1','A2','T1','T2','MAX1','MIN1','K3','A3','A4','T3','T4','MAX3','MIN3','K5','A5','A6','T5','T6','MAX5','MIN5'),
        STAB1=('KoverT', 'T', 'T1overT3', 'T3', 'T2overT4', 'T4', 'HLIM'),
        STAB2A=('K2', 'T2', 'K3', 'T3', 'K4', 'K5', 'T5', 'HLIM'),
        STAB3=('Tt', 'TX1', 'TX2', 'KX', 'VLIM'),
        STAB4=('KX', 'TT', 'TX1', 'TX2', 'Ta', 'Tb', 'Tc', 'Td', 'Te', 'L1', 'L2'),
        STABNI=('K', 'T1', 'T2', 'T0', 'LIMIT'),
        COMP=('Xe',),
        IEEEVC=('RC', 'XC'),
        REMCMP=('JBUS',),
        MNLEX1=('KF2', 'TF2', 'KM', 'TM', 'MELMAX', 'K'),
        MNLEX2=('KF2', 'TF2', 'KM', 'TM', 'MELMAX', 'Q0', 'Radius'),
        MNLEX3=('KF2', 'TF2', 'KM', 'TM', 'MELMAX', 'Q0', 'B'),
        HYGOV2=('KP','KI','KA','T1','T2','T3','T4','T5','T6','TR','r','R','VGMAX','GMAX','GMIN','PMAX'),
        HYGOV=('R', 'r', 'Tr', 'Tf', 'Tg', 'VELM', 'GMAX', 'GMIN', 'Tw', 'At', 'Dturb', 'qNL'),
        IEEEG3=('TG', 'TP', 'UO', 'UC', 'PMAX', 'PMIN', 'SIGMA', 'DELTA', 'TR', 'TW', 'A11', 'A13', 'A21', 'A23'),
        SEXS=('TATB', 'TB', 'K', 'TE', 'EMIN', 'EMAX'),
        EXST1=('TR', 'VIMAX', 'VIMIN', 'TC', 'TB', 'KA', 'TA', 'VRMAX', 'VRMIN', 'KC', 'KF', 'TF'),
        EXST2A=('TR','KA','TA','VRMAX','VRMIN','KE','TE','KF','TF','KP','KI','KC','EFDMAX'),
        ESST2A=('TR','KA','TA','VRMAX','VRMIN','KE','TE','KF','TF','KP','KI','KC','EFDMAX'),
        EXST2=('TR', 'KA', 'TA', 'VRMAX', 'VRMIN', 'KE', 'TE', 'KF', 'TF', 'KP', 'KI', 'KC', 'EFDMAX'),
        ESST4B=('TR','KPR','KIR','VRMAX','VRMIN','TA','KPM','KIM','VMMAX','VMMIN','KG','KP','KI','VBMAX','KC','Xl','THETAP'),
        ESST3A=('TR', 'VIMAX', 'VIMIN', 'KM', 'TC', 'TB', 'KA', 'TA', 'VRMAX', 'VRMIN', 'KG', 'KP', 'KI', 'VBMAX', 'KC', 'XL', 'VGMAX', 'THETAP', 'TM', 'VMMAX', 'VMMIN'),
        IEEET1=('TR', 'KA', 'TA', 'VRMAX', 'VRMIN', 'KE', 'TE', 'KF', 'TF', 'Switch', 'E1', 'SE1', 'E2', 'SE2'),
        ST5B=('TR','TC1','TB1','TC2','TB2','KR','VRMAX','VRMIN','T1','KC','TUC1','TUB1','TUC2','TUB2','TOC1','TOB1','TOC2','TOB2'),
        AC7B=('TR', 'KPR', 'KIR', 'KDR', 'TDR', 'VRMAX', 'VRMIN', 'KPA', 'KIA', 'VAMAX', 'VAMIN', 'KP', 'KL', 'KF1', 'KF2', 'KF3', 'TF3', 'KC', 'KD', 'KE', 'TE', 'VFEMAX', 'VEMIN', 'E1', 'SE1', 'E2', 'SE2'),
        AC8B=('TR','KPR','KIR','KDR','TDR','VPIDMAX','VPIDMIN','KA','TA','VRMAX','VRMIN','KC','KD','KE','TE','VFEMAX','VEMIN','E1','SE1','E2','SE2'),
        EXPIC1=('TR','KA','TA1','VR1','VR2','TA2','TA3','TA4','VRMAX','VRMIN','KF','TF1','TF2','EFDMAX','EFDMIN','KE','TE','E1','SE1','E2','SE2','KP','KI','KC'),
        EXNI=('TR','KA','TA','VRMAX','VRMIN','KF','TF1','TF2','SWITCH','R'),
        IEET1B=('TR','VSMAX','VSMIN','KA','TA1','VRMAX','VRMIN','TA2','KF1','TF1','KE','TE','E1','SE1','E2','SE2','Switch','Xe'),
        IEET1A=('KA', 'TA', 'VRMAX', 'VRMIN', 'KE', 'TE', 'KF', 'TF', 'EFDMIN', 'E1', 'SE1', 'EFDMAX', 'SEMAX'),
        IEEET4=('KR', 'TRH', 'KV', 'VRMAX', 'VRMIN', 'TE', 'KE', 'E1', 'SE1', 'E2', 'SE2'),
        IEEET5=('TRH', 'KV', 'VRMAX', 'VRMIN', 'TE', 'KE', 'E1', 'SE1', 'E2', 'SE2'),
        DC3A=('TR','KV','VRMAX','VRMIN','TRH','TE','KE','VEMIN','E1','SE1','E2','SE2'),
        IEEEX4=('TR', 'TRH', 'KV', 'VRMAX', 'VRMIN', 'TE', 'KE', 'E1', 'SE1', 'E2', 'SE2'),
        IEET5A=('KA', 'TRH', 'KV', 'VRMAX', 'VRMIN', 'TE', 'KE', 'E1', 'SE1', 'E2', 'SE2', 'EFDMAX', 'EFDMIN'),
        IEEET3=('TR','KA','TA','VRMAX','VRMIN','TE','KF','TF','KP','KI','VBMAX','KE'),
        IEEEX3=('TR','KA','TA','VRMAX','VRMIN','TE','KF','TF','KP','KI','VBMAX','KE'),
        IEEET2=('TR', 'KA', 'TA', 'VRMAX', 'VRMIN', 'KE', 'TE', 'KF', 'TF1', 'TF2', 'E1', 'SE1', 'E2', 'SE2'),
        BBSEX1=('TF','K','T1','T2','T3','T4','VRMAX','VRMIN','EFDMAX','EFDMIN','Switch'),
        ESAC8B=('TR','KP','KI','KD','TD','KA','TA','VRMAX','VRMIN','TE','KE','E1','SE1','E2','SE2'),
        ESAC5A=('TR', 'KA', 'TA', 'VRMAX', 'VRMIN', 'KE', 'TE', 'KF', 'TF1', 'TF2', 'TF3', 'E1', 'SE1', 'E2', 'SE2'),
        EXAC4=('TR', 'VIMAX', 'VIMIN', 'TC', 'TB', 'KA', 'TA', 'VRMAX', 'VRMIN', 'KC'),
        ESAC4A=('TR', 'VIMAX', 'VIMIN', 'TC', 'TB', 'KA', 'TA', 'VRMAX', 'VRMIN', 'KC'),
        IEEEX2=('TR', 'KA', 'TA', 'TB', 'TC', 'VRMAX', 'VRMIN', 'KE', 'TE', 'KF', 'TF1', 'TF2', 'E1', 'SE1', 'E2', 'SE2'),
        IEEX2A=('TR', 'KA', 'TA', 'TB', 'TC', 'VRMAX', 'VRMIN', 'KE', 'TE', 'KF', 'TF1', 'E1', 'SE1', 'E2', 'SE2'),
        EXBAS=('TR', 'KP', 'KI', 'KA', 'TA', 'TB', 'TC', 'VRMAX', 'VRMIN', 'KF', 'TF', 'TF1', 'TF2', 'KE', 'TE', 'KC', 'KD', 'E1', 'SE1', 'E2', 'SE2'),
        EXAC1=('TR', 'TB', 'TC', 'KA', 'TA', 'VRMAX', 'VRMIN', 'TE', 'KF', 'TF', 'KC', 'KD', 'KE', 'E1', 'SE1', 'E2', 'SE2'),
        EXAC1A=('TR', 'TB', 'TC', 'KA', 'TA', 'VRMAX', 'VRMIN', 'TE', 'KF', 'TF', 'KC', 'KD', 'KE', 'E1', 'SE1', 'E2', 'SE2'),
        ESAC1A=('TR', 'TB', 'TC', 'KA', 'TA', 'VAMAX', 'VAMIN', 'TE', 'KF', 'TF', 'KC', 'KD', 'KE', 'E1', 'SE1', 'E2', 'SE2', 'VRMAX', 'VRMIN'),
        ESAC2A=('TR', 'TB', 'TC', 'KA', 'TA', 'VAMAX', 'VAMIN', 'KB', 'VRMAX', 'VRMIN', 'TE', 'VFEMAX', 'KH', 'KF', 'TF', 'KC', 'KD', 'KE', 'E1', 'SE1', 'E2', 'SE2'),
        ESAC3A=('TR', 'TB', 'TC', 'KA', 'TA', 'VAMAX', 'VAMIN', 'TE', 'VEMIN', 'KR', 'KF', 'TF', 'KN', 'EFDN', 'KC', 'KD', 'KE', 'VFEMAX', 'E1', 'SE1', 'E2', 'SE2'),
        EXAC2=('TR', 'TB', 'TC', 'KA', 'TA', 'VAMAX', 'VAMIN', 'KB', 'VRMAX', 'VRMIN', 'TE', 'KL', 'KH', 'KF', 'TF', 'KC', 'KD', 'KE', 'VLR', 'E1', 'SE1', 'E2', 'SE2'),
        EXAC3=('TR', 'TB', 'TC', 'KA', 'TA', 'VAMAX', 'VAMIN', 'TE', 'KLV', 'KR', 'KF', 'TF', 'KN', 'EFDN', 'KC', 'KD', 'KE', 'VLV', 'E1', 'SE1', 'E2', 'SE2'),
        ESDC2A=('TR', 'KA', 'TA', 'TB', 'TC', 'VRMAX', 'VRMIN', 'KE', 'TE', 'KF', 'TF1', 'Switch', 'E1', 'SE1', 'E2', 'SE2'),
        ESDC1A=('TR', 'KA', 'TA', 'TB', 'TC', 'VRMAX', 'VRMIN', 'KE', 'TE', 'KF', 'TF1', 'Switch', 'E1', 'SE1', 'E2', 'SE2'),
        EXDC2=('TR', 'KA', 'TA', 'TB', 'TC', 'VRMAX', 'VRMIN', 'KE', 'TE', 'KF', 'TF1', 'Switch', 'E1', 'SE1', 'E2', 'SE2'),
        IEEEX1=('TR', 'KA', 'TA', 'TB', 'TC', 'VRMAX', 'VRMIN', 'KE', 'TE', 'KF1', 'TF1', 'Switch', 'E1', 'SE1', 'E2', 'SE2'),
    )
    return layouts.get(model.upper(), None)
