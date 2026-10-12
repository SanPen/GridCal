/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 * SPDX-License-Identifier: MPL-2.0
 */
#include <stdint.h>
#include <stdio.h>
#ifdef _WIN32
#define VG_OEM_EXPORT __declspec(dllexport)
#define VG_OEM_CDECL __cdecl
#else
#define VG_OEM_EXPORT __attribute__((visibility("default")))
#define VG_OEM_CDECL
#endif

typedef union Extension { double real64; void *pointer; uint8_t bytes[8]; } Extension;
typedef struct InputInfo { const char *name; const char *path; int32_t width; const char *unit; int32_t semantic; } InputInfo;
typedef struct OutputInfo { const char *name; const char *path; int32_t width; const char *unit; int32_t semantic; } OutputInfo;
typedef struct ParameterInfo { const char *name; const char *description; const char *unit; double default_value; double minimum_value; double maximum_value; int32_t fixed_value; } ParameterInfo;
typedef struct ModelInfo {
    uint8_t release[4]; const char *name; const char *version; const char *description;
    const char *version_control; const char *general; const char *created; const char *creator;
    const char *modified_date; const char *modified_by; const char *modified_comment;
    const char *modified_history; const char *generated; const char *solver; double sample_time;
    int32_t input_count; const InputInfo *inputs; int32_t output_count; const OutputInfo *outputs;
    int32_t parameter_count; const ParameterInfo *parameters; int32_t continuous_states;
    int32_t miscellaneous_bytes; uint32_t checksum[4]; const char *last_error;
    uint8_t mode; uint8_t loadflow; int32_t int_states; int32_t float_states;
    int32_t double_states; Extension extension;
} ModelInfo;
typedef struct Instance {
    double *inputs; double *outputs; double *parameters; double *continuous_states;
    double *derivatives; uint8_t *miscellaneous; const char *last_error;
    const char *last_general; uint8_t verbose; int32_t *int_states;
    float *float_states; double *double_states; Extension extension;
} Instance;

VG_OEM_EXPORT const ModelInfo *VG_OEM_CDECL Model_GetInfo(void) {
    static const InputInfo inputs[2] = {
        {"u", "In0", 1, "pu", 90},
        {"in_vec", "In1", 3, "pu", 90}
    };
#ifdef CONTROL_RESPONSE
    static const OutputInfo outputs[2] = {
        {"terminal_voltage_reference", "Out0", 1, "pu", 90},
        {"out_vec", "Out1", 3, "pu", 90}
    };
#else
    static const OutputInfo outputs[2] = {
        {"y", "Out0", 1, "pu", 90},
        {"out_vec", "Out1", 3, "pu", 90}
    };
#endif
    static const ParameterInfo parameters[2] = {
        {"gain", "Test gain", "pu", 2.0, 1.0, 3.0, 0},
        {"y0", "Initial output", "pu", 0.0, -10.0, 10.0, 0}
    };
    static const ModelInfo info = {
        {1, 0, 0, 0}, "LegacyFixture", "1", "IEEE/CIGRE 1.0 fixture", "test", "test",
        "2026-09-18", "VeraGrid", "2026-09-18", "VeraGrid", "", "", "clang", "discrete",
        0.0003, 2, inputs, 2, outputs, 2, parameters, 0, 0, {0, 0, 0, 0}, "", 1, 0,
        0, 0, 5000, {0}
    };
    return &info;
}

VG_OEM_EXPORT Instance *VG_OEM_CDECL Model_Instance(
        uint32_t use_internal_solver,
        double communication_step) {
    /* Legacy deliveries may retain this deprecated export while the host owns
       the complete instance structure. The adapter must not call it. */
    (void)use_internal_solver;
    (void)communication_step;
    return NULL;
}

VG_OEM_EXPORT const char *VG_OEM_CDECL Model_CheckParameters(Instance *instance) {
    return instance->parameters[0] >= 1.0 && instance->parameters[0] <= 3.0 ? NULL : "gain out of range";
}
VG_OEM_EXPORT const char *VG_OEM_CDECL Model_Initialize(Instance *instance) {
    instance->double_states[0] = instance->parameters[1];
#ifdef CONTROL_RESPONSE
    instance->outputs[0] = 0.95;
#else
    instance->outputs[0] = instance->parameters[1];
#endif
    instance->outputs[1] = instance->inputs[1];
    instance->outputs[2] = instance->inputs[2];
    instance->outputs[3] = instance->inputs[3];
    return NULL;
}
VG_OEM_EXPORT const char *VG_OEM_CDECL Model_Outputs(Instance *instance, uint32_t major_step) {
    static const char no_error[1] = {0};
#ifdef CONTROL_RESPONSE
    (void)major_step;
    instance->outputs[0] = instance->inputs[0] < 1.5 ? 0.95 : 1.05;
#else
    instance->double_states[0] += major_step == 0 ? 0.0 : 1.0;
    instance->outputs[0] = instance->inputs[0] * instance->parameters[0] + instance->double_states[0];
#endif
    instance->outputs[1] = instance->inputs[1];
    instance->outputs[2] = instance->inputs[2];
    instance->outputs[3] = instance->inputs[3];
    return no_error;
}
VG_OEM_EXPORT const char *VG_OEM_CDECL Model_Update(Instance *instance) { (void)instance; return NULL; }
VG_OEM_EXPORT const char *VG_OEM_CDECL Model_Loadflow(Instance *instance) { (void)instance; return NULL; }
VG_OEM_EXPORT const char *VG_OEM_CDECL Model_Derivatives(Instance *instance) { (void)instance; return NULL; }
VG_OEM_EXPORT const char *VG_OEM_CDECL Model_Terminate(Instance *instance) { (void)instance; return NULL; }
VG_OEM_EXPORT const char *VG_OEM_CDECL Model_PrintInfo(void) { printf("LegacyFixture\n"); return NULL; }
