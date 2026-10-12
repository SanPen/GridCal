/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 * SPDX-License-Identifier: MPL-2.0
 */
#include <stdint.h>
#include <stdlib.h>
#ifdef _WIN32
#define VG_OEM_EXPORT __declspec(dllexport)
#define VG_OEM_CDECL __cdecl
#else
#define VG_OEM_EXPORT __attribute__((visibility("default")))
#define VG_OEM_CDECL
#endif

typedef union Extension { double real64; void *pointer; uint8_t bytes[8]; } Extension;
typedef struct SignalInfo { const char *name; const char *path; int32_t width; } SignalInfo;
typedef struct ParameterInfo { const char *name; const char *description; const char *unit; double default_value; double minimum_value; double maximum_value; } ParameterInfo;
typedef struct ModelInfo {
    uint8_t release[4]; const char *name; const char *version; const char *description;
    const char *version_control; const char *general; const char *created; const char *creator;
    const char *modified_date; const char *modified_by; const char *modified_comment;
    const char *modified_history; const char *generated; const char *solver; double sample_time;
    int32_t input_count; const SignalInfo *inputs; int32_t output_count; const SignalInfo *outputs;
    int32_t parameter_count; const ParameterInfo *parameters; int32_t continuous_states;
    int32_t miscellaneous_bytes; uint32_t checksum[4]; const char *last_error;
    uint8_t mode; uint8_t loadflow; Extension extension;
} ModelInfo;
typedef struct Instance {
    double *inputs; double *outputs; double *parameters; double *continuous_states;
    double *derivatives; uint8_t *miscellaneous; const char *last_error;
    const char *last_general; uint8_t verbose; Extension extension;
} Instance;

VG_OEM_EXPORT const ModelInfo *VG_OEM_CDECL Model_GetInfo(void) {
    static const SignalInfo inputs[1] = {{"u", "In0", 1}};
#ifdef CONTROL_RESPONSE
    static const SignalInfo outputs[1] = {{"terminal_voltage_reference", "Out0", 1}};
#else
    static const SignalInfo outputs[1] = {{"y", "Out0", 1}};
#endif
    static const ParameterInfo parameters[1] = {{"gain", "Test gain", "pu", 2.0, 1.0, 3.0}};
    static const ModelInfo info = {
        {1, 0, 0, 0}, "IecEseFixture", "1", "IEC ESE fixture", "test", "test",
        "2026-09-18", "VeraGrid", "2026-09-18", "VeraGrid", "", "", "clang", "internal",
        0.0002, 1, inputs, 1, outputs, 1, parameters, 0, 0, {0, 0, 0, 0}, "", 1, 0, {0}
    };
    return &info;
}

VG_OEM_EXPORT Instance *VG_OEM_CDECL Model_Instance(uint32_t use_internal_solver, double ta) {
    Instance *instance;
    if (use_internal_solver != 1U || ta != 0.0002) return NULL;
    instance = (Instance *)calloc(1, sizeof(Instance));
    if (instance == NULL) return NULL;
    instance->inputs = (double *)calloc(1, sizeof(double));
    instance->outputs = (double *)calloc(1, sizeof(double));
    instance->parameters = (double *)calloc(1, sizeof(double));
    if (instance->inputs == NULL || instance->outputs == NULL || instance->parameters == NULL) return NULL;
    instance->extension.real64 = ta;
    return instance;
}
VG_OEM_EXPORT const char *VG_OEM_CDECL Model_CheckParameters(Instance *instance) { return instance->parameters[0] >= 1.0 && instance->parameters[0] <= 3.0 ? NULL : "gain out of range"; }
VG_OEM_EXPORT const char *VG_OEM_CDECL Model_Initialize(Instance *instance) {
#ifdef CONTROL_RESPONSE
    instance->outputs[0] = 0.95;
#else
    instance->outputs[0] = 0.0;
#endif
    return NULL;
}
VG_OEM_EXPORT const char *VG_OEM_CDECL Model_Outputs(Instance *instance, uint32_t major_step) {
#ifdef CONTROL_RESPONSE
    (void)major_step;
    instance->outputs[0] = instance->inputs[0] < 1.5 ? 0.95 : 1.05;
#else
    instance->outputs[0] = instance->inputs[0] * instance->parameters[0] + instance->extension.real64 + (double)major_step;
#endif
    return NULL;
}
VG_OEM_EXPORT const char *VG_OEM_CDECL Model_Update(Instance *instance) { (void)instance; return NULL; }
VG_OEM_EXPORT const char *VG_OEM_CDECL Model_Loadflow(Instance *instance) { (void)instance; return NULL; }
VG_OEM_EXPORT const char *VG_OEM_CDECL Model_Derivatives(Instance *instance) { (void)instance; return NULL; }
VG_OEM_EXPORT const char *VG_OEM_CDECL Model_Terminate(Instance *instance) {
    free(instance->inputs);
    free(instance->outputs);
    free(instance->parameters);
    free(instance);
    return NULL;
}
