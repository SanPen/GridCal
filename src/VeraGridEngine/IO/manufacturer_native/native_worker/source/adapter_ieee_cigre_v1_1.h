/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 * SPDX-License-Identifier: MPL-2.0
 */
#ifndef VERAGRID_ADAPTER_IEEE_CIGRE_V1_1_H
#define VERAGRID_ADAPTER_IEEE_CIGRE_V1_1_H

#include <stdint.h>
#include "platform.h"

typedef union IEEE_Cigre_DLLInterface_Default_Value {
    char Char_Val;
    char *Char_Ptr;
    int8_t Int8_Val;
    uint8_t Uint8_Val;
    int16_t Int16_Val;
    uint16_t Uint16_Val;
    int32_t Int32_Val;
    uint32_t Uint32_Val;
    float Real32_Val;
    double Real64_Val;
} IEEE_Cigre_DLLInterface_Default_Value;

typedef union IEEE_Cigre_DLLInterface_MinMax_Value {
    char Char_Val;
    int8_t Int8_Val;
    uint8_t Uint8_Val;
    int16_t Int16_Val;
    uint16_t Uint16_Val;
    int32_t Int32_Val;
    uint32_t Uint32_Val;
    float Real32_Val;
    double Real64_Val;
} IEEE_Cigre_DLLInterface_MinMax_Value;

typedef struct IEEE_Cigre_DLLInterface_Signal {
    char *Name;
    char *Description;
    char *Unit;
    int DataType;
    int32_t Width;
} IEEE_Cigre_DLLInterface_Signal;

typedef struct IEEE_Cigre_DLLInterface_Parameter {
    char *Name;
    char *GroupName;
    char *Description;
    char *Unit;
    int DataType;
    int32_t FixedValue;
    IEEE_Cigre_DLLInterface_Default_Value DefaultValue;
    IEEE_Cigre_DLLInterface_MinMax_Value MinValue;
    IEEE_Cigre_DLLInterface_MinMax_Value MaxValue;
} IEEE_Cigre_DLLInterface_Parameter;

typedef struct IEEE_Cigre_DLLInterface_Model_Info {
    uint8_t DLLInterfaceVersion[4];
    char *ModelName;
    char *ModelVersion;
    char *ModelDescription;
    char *GeneralInformation;
    char *ModelCreated;
    char *ModelCreator;
    char *ModelLastModifiedDate;
    char *ModelLastModifiedBy;
    char *ModelModifiedComment;
    char *ModelModifiedHistory;
    double FixedStepBaseSampleTime;
    uint8_t EMT_RMS_Mode;
    int32_t NumInputPorts;
    IEEE_Cigre_DLLInterface_Signal *InputPortsInfo;
    int32_t NumOutputPorts;
    IEEE_Cigre_DLLInterface_Signal *OutputPortsInfo;
    int32_t NumParameters;
    IEEE_Cigre_DLLInterface_Parameter *ParametersInfo;
    int32_t NumIntStates;
    int32_t NumFloatStates;
    int32_t NumDoubleStates;
} IEEE_Cigre_DLLInterface_Model_Info;

typedef struct IEEE_Cigre_DLLInterface_Instance {
    void *ExternalInputs;
    void *ExternalOutputs;
    void *Parameters;
    double Time;
    uint8_t SimTool_EMT_RMS_Mode;
    char *LastErrorMessage;
    char *LastGeneralMessage;
    int32_t *IntStates;
    float *FloatStates;
    double *DoubleStates;
} IEEE_Cigre_DLLInterface_Instance;

typedef IEEE_Cigre_DLLInterface_Model_Info *(VG_PLATFORM_CDECL *VgModelGetInfo)(void);
typedef int32_t (VG_PLATFORM_CDECL *VgModelInstanceCall)(IEEE_Cigre_DLLInterface_Instance *);
typedef int32_t (VG_PLATFORM_CDECL *VgModelPrintInfo)(void);

#endif
