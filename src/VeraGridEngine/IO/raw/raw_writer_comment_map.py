# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

# Comments map for Raw writer per versions

comment_version_map = {
    35: {
        "BUS": "@!   I,'NAME        ', BASKV, IDE,AREA,ZONE,OWNER, VM,        VA,    NVHI,   NVLO,   EVHI,   "
               "EVLO\n",
        "LOAD": "@!   I,'ID',STAT,AREA,ZONE,      PL,        QL,"
                "        IP,        IQ,        YP,        YQ, OWNER,"
                "SCALE,INTRPT,  DGENP,     DGENQ,DGENF,'  LOAD TYPE '\n",
        "FIXED SHUNT": "@!   I,'ID',STATUS,  GL,        BL\n",
        "GENERATOR": "@!   I,'ID',      PG,        QG,        QT,"
                     "        QB,     VS,    IREG,NREG,     MBASE,     ZR,      "
                     "   ZX,         RT,         XT,     GTAP,STAT,"
                     " RMPCT,      PT,        PB,BASLOD,O1,    F1,  O2,    "
                     "F2,  O3,    F3,  O4,    F4,WMOD, WPF\n",
        "BRANCH": "@!   I,     J,'CKT',      R,           X,       B,"
                  "                   'N A M E'                 ,  "
                  "RATE1,  RATE2,  RATE3,  RATE4,  RATE5,  RATE6,  RATE7,"
                  "  RATE8,  RATE9, RATE10, RATE11, RATE12,   GI, "
                  "     BI,      GJ,      BJ,STAT,MET, LEN,  O1,  F1,    O2,"
                  "  F2,    O3,  F3,    O4,  F4\n",
        "SYSTEM SWITCHING DEVICE": "@!   I,     J,'CKT',          X,  RATE1,"
                                   "  RATE2,  RATE3,  RATE4,  RATE5,  RATE6,  RATE7,  RATE8,  "
                                   "RATE9, RATE10, RATE11, RATE12, STAT,NSTAT,  MET,STYPE,'NAME'\n",
        "TRANSFORMER": "@!   I,     J,     K,'CKT',CW,CZ,CM,     MAG1,        MAG2,NMETR,               'N A M E',"
                       "               STAT,O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4,     'VECGRP', ZCOD\n"
                       "@!   R1-2,       X1-2, SBASE1-2,     R2-3,"
                       "       X2-3, SBASE2-3,     R3-1,       X3-1, SBASE3-1,"
                       " VMSTAR,   ANSTAR\n"
                       "@!WINDV1, NOMV1,   ANG1, RATE1-1, RATE1-2,"
                       " RATE1-3, RATE1-4, RATE1-5, RATE1-6, RATE1-7, RATE1-8,"
                       " RATE1-9,RATE1-10,RATE1-11,RATE1-12,COD1,CONT1,NOD1,  RMA1,   RMI1,"
                       "   VMA1,   VMI1, NTP1,TAB1, CR1,    CX1,  CNXA1\n"
                       "@!WINDV2, NOMV2,   ANG2, RATE2-1, RATE2-2,"
                       " RATE2-3, RATE2-4, RATE2-5, RATE2-6, RATE2-7, RATE2-8,"
                       " RATE2-9,RATE2-10,RATE2-11,RATE2-12,COD2,CONT2,NOD2,  RMA2,   RMI2,"
                       "   VMA2,   VMI2, NTP2,TAB2, CR2,    CX2,  CNXA2\n"
                       "@!WINDV3, NOMV3,   ANG3, RATE3-1, RATE3-2,"
                       " RATE3-3, RATE3-4, RATE3-5, RATE3-6, RATE3-7, RATE3-8, "
                       "RATE3-9,RATE3-10,RATE3-11,RATE3-12,COD3,CONT3,"
                       "NOD3,  RMA3,   RMI3,   VMA3,   VMI3, NTP3,TAB3, CR3,   "
                       " CX3,  CNXA3\n",
        "AREA INTERCHANGE": "@! I,   ISW,    PDES,     PTOL,    'ARNAME'\n",
        "TWO-TERMINAL DC LINE": "@!  'NAME',   MDC,    RDC,     SETVL,    VSCHD,    VCMOD,    RCOMP,   DELTI,"
                                "METER   DCVMIN,CCCITMX,"
                                "CCCACC\n"
                                "@! IPR,NBR,  ANMXR,  ANMNR,   RCR,    XCR,"
                                "   EBASR,  TRR,    TAPR,   TMXR,   TMNR,   STPR,    ICR,"
                                "NDR,   IFR,   ITR,'IDR', XCAPR\n"
                                "@! IPI,NBI,  ANMXI,  ANMNI,   RCI,    XCI,"
                                "   EBASI,  TRI,    TAPI,   TMXI,   TMNI,   STPI,    ICI,"
                                "NDI,   IFI,   ITI,'IDI', XCAPI\n",
        "VSC DC LINE": "@!  'NAME',   MDC,  RDC,   O1,  F1,    O2,  F2,    O3,  F3,    O4,  F4\n"
                       "@!IBUS,TYPE,MODE,  DCSET,  ACSET,  ALOSS,  BLOSS,MINLOSS,  SMAX,   IMAX,"
                       "   PWF,     MAXQ,   MINQ, \n"
                       "VSREG,NREG, RMPCT\n",
        "IMPEDANCE CORRECTION": "@!I,  T1,   Re(F1), Im(F1),   T2,   Re(F2), Im(F2),"
                                "   T3,   Re(F3), Im(F3),   T4,   Re(F4), Im(F4),  "
                                " T5,   Re(F5), Im(F5),   T6,   Re(F6), Im(F6)\n"
                                "@!    T7,   Re(F7), Im(F7),   T8,   Re(F8), Im(F8),"
                                "   T9,   Re(F9), Im(F9),   T10, Re(F10),Im(F10),  "
                                " T11, Re(F11),Im(F11),   T12, Re(F12),Im(F12)\n"
                                "@!      ...\n",
        "MULTI-TERMINAL DC LINE": "@!  'NAME',    NCONV,NDCBS,NDCLN,  MDC, VCONV,   VCMOD, VCONVN\n"
                                  "@!  IB, N,  ANGMX,  ANGMN,   RC,     XC,     EBAS,   TR,    TAP,"
                                  "    TPMX,   TPMN,   TSTP,   SETVL,   "
                                  "DCPF,  MARG,CNVCOD\n"
                                  "@!IDC, IB,AREA,ZONE,   'DCNAME',  IDC2, RGRND,OWNER\n"
                                  "@!IDC,JDC,'DCCKT',MET,  RDC,      LDC\n",
        "MULTI-SECTION LINE GROUP": "@!   I,     J,'ID',MET,DUM1,  DUM2,  DUM3,  DUM4,"
                                    "  DUM5,  DUM6,  DUM7,  DUM8,  DUM9\n",
        "ZONE": "@! I,   'ZONAME'\n",
        "INTER-AREA TRANSFER": "@!ARFROM,ARTO,'TRID',PTRAN\n",
        "OWNER": "@! I,   'OWNAME'\n",
        "FACTS DEVICE": "@!  'NAME',         I,     J,MODE,PDES,   QDES,  VSET,   SHMX,   TRMX,   VTMN,"
                        "   VTMX,   VSMX,    "
                        "IMX,   LINX,   RMPCT,OWNER,  SET1,    SET2,VSREF, FCREG,NREG,   'MNAME'\n",
        "SWITCHED SHUNT": "@!   I,'ID',MODSW,ADJM,ST, VSWHI,  VSWLO, SWREG,NREG, RMPCT,   'RMIDNT',     BINIT,"
                          "S1,N1,    B1, S2,"
                          "N2,    B2, S3,N3,    B3, S4,N4,    B4, S5,N5,    B5, S6,N6,    B6, S7,N7,"
                          "    B7, S8,N8,    B8\n",
        "GNE": "@!  'NAME',        'MODEL',     NTERM,BUS1...BUSNTERM,NREAL,NINTG,NCHAR\n"
               "@!ST,OWNER,NMETR\n"
               "@! REAL1...REAL(MIN(10,NREAL))\n"
               "@! INTG1...INTG(MIN(10,NINTG))\n"
               "@! CHAR1...CHAR(MIN(10,NCHAR))\n",

    }
}
