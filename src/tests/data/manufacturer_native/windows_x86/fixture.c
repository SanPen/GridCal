/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 * SPDX-License-Identifier: MPL-2.0
 */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

#include "../../../../VeraGridEngine/data/native_worker/source/adapter_ieee_cigre_v1_1.h"

__declspec(dllexport) IEEE_Cigre_DLLInterface_Model_Info *__cdecl Model_GetInfo(void) {
#ifdef NULL_GET_INFO
    return NULL;
#else
    IEEE_Cigre_DLLInterface_Model_Info *info =
        (IEEE_Cigre_DLLInterface_Model_Info *)calloc(1, sizeof(*info));
    IEEE_Cigre_DLLInterface_Signal *inputs =
        (IEEE_Cigre_DLLInterface_Signal *)calloc(2, sizeof(*inputs));
    IEEE_Cigre_DLLInterface_Signal *outputs =
        (IEEE_Cigre_DLLInterface_Signal *)calloc(1, sizeof(*outputs));
    IEEE_Cigre_DLLInterface_Parameter *parameters =
        (IEEE_Cigre_DLLInterface_Parameter *)calloc(2, sizeof(*parameters));
    if (info == NULL || inputs == NULL || outputs == NULL || parameters == NULL) return NULL;
    info->DLLInterfaceVersion[0] = 1;
    info->DLLInterfaceVersion[1] = 1;
    info->ModelName = "GoldenModel";
    info->ModelVersion = "v1.7";
    info->ModelDescription = "Protocol oracle model";
    info->GeneralInformation = "independent metadata";
    info->ModelCreated = "2026-09-18T01:02:03Z";
    info->ModelCreator = "eRoots Oracle";
    info->ModelLastModifiedDate = "2026-09-18T04:05:06Z";
    info->ModelLastModifiedBy = "Independent Reviewer";
    info->ModelModifiedComment = "distinct comment";
    info->ModelModifiedHistory = "distinct history";
    info->FixedStepBaseSampleTime = 0.000005;
    info->EMT_RMS_Mode = 3;
    inputs[0].Name = "u_fast";
    inputs[0].Description = "two float inputs";
    inputs[0].Unit = "pu";
    inputs[0].DataType = 8;
    inputs[0].Width = 2;
    inputs[1].Name = "u_count";
    inputs[1].Description = "one unsigned input";
    inputs[1].Unit = "count";
    inputs[1].DataType = 7;
    inputs[1].Width = 1;
    outputs[0].Name = "y_power";
    outputs[0].Description = "one double output";
    outputs[0].Unit = "MW";
    outputs[0].DataType = 9;
    outputs[0].Width = 1;
    parameters[0].Name = "gain";
    parameters[0].GroupName = "control";
    parameters[0].Description = "signed gain";
    parameters[0].Unit = "pu";
    parameters[0].DataType = 6;
    parameters[0].FixedValue = 0;
    parameters[0].DefaultValue.Int32_Val = 7;
    parameters[0].MinValue.Int32_Val = -101;
    parameters[0].MaxValue.Int32_Val = 303;
    parameters[1].Name = "mode";
    parameters[1].GroupName = "control";
    parameters[1].Description = "mode text";
    parameters[1].Unit = "";
    parameters[1].DataType = 10;
    parameters[1].FixedValue = 1;
    parameters[1].DefaultValue.Char_Ptr = "mode-a";
    info->NumInputPorts = 2;
    info->InputPortsInfo = inputs;
    info->NumOutputPorts = 1;
    info->OutputPortsInfo = outputs;
    info->NumParameters = 2;
    info->ParametersInfo = parameters;
    info->NumIntStates = 11;
    info->NumFloatStates = 22;
    info->NumDoubleStates = 33;
    return info;
#endif
}

__declspec(dllexport) int32_t __cdecl Model_FirstCall(IEEE_Cigre_DLLInterface_Instance *instance) {
    instance->LastErrorMessage = "err-1";
    instance->LastGeneralMessage = "info-1";
    return 0;
}

__declspec(dllexport) int32_t __cdecl Model_CheckParameters(IEEE_Cigre_DLLInterface_Instance *instance) {
    instance->LastErrorMessage = "err-2";
    instance->LastGeneralMessage = "info-2";
#ifdef QUALIFIED
    return 0;
#else
    return 1;
#endif
}

__declspec(dllexport) int32_t __cdecl Model_Initialize(IEEE_Cigre_DLLInterface_Instance *instance) {
    instance->LastErrorMessage = "err-3";
    instance->LastGeneralMessage = "info-3";
#ifdef QUALIFIED
    return 0;
#else
    return 2;
#endif
}

__declspec(dllexport) int32_t __cdecl Model_Outputs(IEEE_Cigre_DLLInterface_Instance *instance) {
    double *output = (double *)instance->ExternalOutputs;
    instance->LastErrorMessage = instance->Time == 0.0 ? "err-4" : "sample-err";
    instance->LastGeneralMessage = instance->Time == 0.0 ? "info-4" : "sample-info";
    output[0] = instance->Time == 0.0 ? 0.25 : 0.5;
#ifdef CRASH_ON_SAMPLE
    if (instance->Time > 0.0) ExitProcess(99);
#elif defined(HANG_ON_SAMPLE)
    if (instance->Time > 0.0) {
        for (;;) {}
    }
#elif defined(NAN_ON_SAMPLE)
    if (instance->Time > 0.0) output[0] = NAN;
#elif defined(FAIL_ON_SAMPLE)
    if (instance->Time > 0.0) return 9;
#endif
#ifdef QUALIFIED
    return 0;
#else
    return instance->Time == 0.0 ? 3 : 1;
#endif
}

__declspec(dllexport) int32_t __cdecl Model_Iterate(IEEE_Cigre_DLLInterface_Instance *instance) {
    instance->LastErrorMessage = "";
    instance->LastGeneralMessage = "";
    return 0;
}

__declspec(dllexport) int32_t __cdecl Model_Terminate(IEEE_Cigre_DLLInterface_Instance *instance) {
    instance->LastErrorMessage = "terminate-err";
    instance->LastGeneralMessage = "terminate-info";
    return 0;
}

__declspec(dllexport) int32_t __cdecl Model_PrintInfo(void) {
    fputs("golden stdout\n", stdout);
    fputs("golden stderr\n", stderr);
    fflush(stdout);
    fflush(stderr);
#ifdef QUALIFIED
    return 0;
#else
    return 7;
#endif
}
