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

#include "protocol.h"
#include "platform.h"
#include "adapter_ieee_cigre_v1_1.h"
#include "adapter_ieee_cigre_v1_0.h"
#include "adapter_iec_ese.h"

typedef struct VgNativeInstance {
    char *identifier;
    IEEE_Cigre_DLLInterface_Instance abi;
    uint8_t *inputs;
    uint8_t *outputs;
    uint8_t *parameters;
    char **strings;
    uint32_t string_count;
    uint32_t *input_offsets;
    uint8_t *input_types;
    uint32_t input_count;
    uint32_t *output_offsets;
    uint8_t *output_types;
    uint32_t output_count;
    uint32_t *parameter_offsets;
    int started;
    int terminated;
} VgNativeInstance;

typedef struct VgNativeWorkerContext {
    VgPlatformChannel request_read;
    VgPlatformChannel response_write;
    VgPlatformCapture capture;
    VgNativeWorkerState state;
    uint32_t last_request_id;
    int has_request_id;
    uint8_t interface_kind;
    uint64_t maximum_frame;
    uint64_t maximum_binary;
    uint32_t maximum_instances;
    uint32_t maximum_ports;
    uint32_t maximum_parameters;
    uint64_t maximum_scalar_slots;
    uint64_t maximum_state_scalars;
    uint64_t maximum_instance_bytes;
    uint64_t maximum_worker_bytes;
    uint64_t maximum_metadata_text;
    uint64_t maximum_capture;
    uint64_t maximum_observations;
    VgPlatformModuleGuard module_guard;
    uint64_t staged_size;
    uint8_t staged_sha256[32];
    uint8_t raw_model_sha256[32];
    uint8_t worker_sha256[32];
    char staged_path[32768];
    char system_path[32768];
    VgPlatformFile staged_file;
    VgPlatformLibrary vendor;
    IEEE_Cigre_DLLInterface_Model_Info *model_info;
    uint8_t *raw_model_info;
    uint64_t raw_model_info_size;
    VgModelGetInfo model_get_info;
    VgModelInstanceCall model_first_call;
    VgModelInstanceCall model_check_parameters;
    VgModelInstanceCall model_initialize;
    VgModelInstanceCall model_outputs;
    VgModelInstanceCall model_iterate;
    VgModelInstanceCall model_terminate;
    VgModelPrintInfo model_print_info;
    VgNativeInstance **instances;
    uint32_t instance_count;
    VgIeeeCigreV10Adapter ieee_cigre_v1_0;
    VgIecEseAdapter iec_ese;
} VgNativeWorkerContext;

void destroy_instance(VgNativeInstance *instance);

#define VG_REQUIRE(REMAINING, N) do { if ((uint64_t)(REMAINING) < (uint64_t)(N)) return VG_NATIVE_BAD_PAYLOAD; } while (0)
#define VG_READ_U32(P, R, OUT) do { VG_REQUIRE((R), 4); memcpy(&(OUT), (P), 4); (P) += 4; (R) -= 4; } while (0)
#define VG_READ_U64(P, R, OUT) do { VG_REQUIRE((R), 8); memcpy(&(OUT), (P), 8); (P) += 8; (R) -= 8; } while (0)
#define VG_APPEND(P, C, LIMIT, SOURCE, N) do { if ((uint64_t)(C) + (uint64_t)(N) > (uint64_t)(LIMIT)) return VG_NATIVE_BAD_PAYLOAD; memcpy((P) + (C), (SOURCE), (size_t)(N)); (C) += (uint64_t)(N); } while (0)
#define VG_APPEND_U32(P, C, LIMIT, VALUE) do { uint32_t vg_value_u32 = (uint32_t)(VALUE); VG_APPEND((P), (C), (LIMIT), &vg_value_u32, 4); } while (0)
#define VG_APPEND_U64(P, C, LIMIT, VALUE) do { uint64_t vg_value_u64 = (uint64_t)(VALUE); VG_APPEND((P), (C), (LIMIT), &vg_value_u64, 8); } while (0)
#define VG_APPEND_TEXT(P, C, LIMIT, TEXT) do { const char *vg_text = (TEXT) == NULL ? "" : (TEXT); uint64_t vg_text_size = 0; if (!vg_native_bounded_text_size(vg_text, 16777216U, &vg_text_size)) return VG_NATIVE_ABI_FAILURE; VG_APPEND_U32((P), (C), (LIMIT), vg_text_size); VG_APPEND((P), (C), (LIMIT), vg_text, vg_text_size); } while (0)

int hash_bytes(const uint8_t *bytes, uint64_t size, uint8_t digest[32]) {
    VgPlatformSha256 hash_context;
    if ((bytes == NULL && size != 0) || digest == NULL) {
        return 0;
    }
    vg_platform_sha256_initialize(&hash_context);
    if (!vg_platform_sha256_update(&hash_context, bytes, size)) {
        return 0;
    }
    return vg_platform_sha256_finalize(&hash_context, digest);
}
int checked_add_size(uint64_t left, uint64_t right, uint64_t *result) {
    if (result == NULL || UINT64_MAX - left < right) {
        return 0;
    }
    *result = left + right;
    return 1;
}

int checked_multiply_size(uint64_t left, uint64_t right, uint64_t *result) {
    if (result == NULL || (left != 0 && right > UINT64_MAX / left)) {
        return 0;
    }
    *result = left * right;
    return 1;
}

int read_frame(VgNativeWorkerContext *context, uint8_t **body, uint64_t *body_size) {
    uint8_t outer[8];
    uint32_t received = 0;
    int ok;
    if (context == NULL || body == NULL || body_size == NULL) {
        return -1;
    }
    ok = vg_platform_channel_read_some(&context->request_read, outer, 8, &received);
    if (!ok || received == 0) {
        return 0;
    }
    while (received < 8) {
        uint32_t part = 0;
        ok = vg_platform_channel_read_some(&context->request_read, outer + received,
                                           8U - received, &part);
        if (!ok || part == 0) {
            return -1;
        }
        received += part;
    }
    memcpy(body_size, outer, 8);
    if (*body_size < sizeof(VgNativeFrameHeader) || *body_size > context->maximum_frame) {
        return -1;
    }
    *body = (uint8_t *)malloc((size_t)*body_size);
    if (*body == NULL) {
        return -1;
    }
    if (!vg_platform_channel_read_exact(&context->request_read, *body, *body_size)) {
        free(*body);
        *body = NULL;
        return -1;
    }
    return 1;
}

int write_response(VgNativeWorkerContext *context, uint8_t opcode, uint32_t request_id,
                   VgNativeStatus status, const uint8_t *payload, uint64_t payload_size) {
    VgNativeFrameHeader header;
    uint64_t body_size;
    if (context == NULL || !checked_add_size(sizeof(header), payload_size, &body_size)
            || body_size > context->maximum_frame) {
        return 0;
    }
    memcpy(header.magic, "VGX1", 4);
    header.version = 1;
    header.kind = VG_NATIVE_RESPONSE;
    header.opcode = opcode;
    header.request_id = request_id;
    header.status = (uint32_t)status;
    header.payload_length = payload_size;
    if (!vg_platform_channel_write_exact(&context->response_write, (const uint8_t *)&body_size, 8)
            || !vg_platform_channel_write_exact(&context->response_write, (const uint8_t *)&header, sizeof(header))) {
        return 0;
    }
    if (payload_size > 0 && !vg_platform_channel_write_exact(&context->response_write, payload, payload_size)) {
        return 0;
    }
    return 1;
}

VgNativeStatus decode_header(VgNativeWorkerContext *context, const uint8_t *body, uint64_t body_size,
                          VgNativeFrameHeader *header, const uint8_t **payload) {
    uint32_t expected_id;
    if (context == NULL || body == NULL || header == NULL || payload == NULL
            || body_size < sizeof(VgNativeFrameHeader)) {
        return VG_NATIVE_BAD_LENGTH;
    }
    memcpy(header, body, sizeof(*header));
    if (memcmp(header->magic, "VGX1", 4) != 0) {
        return VG_NATIVE_BAD_MAGIC;
    }
    if (header->version != 1) {
        return VG_NATIVE_BAD_VERSION;
    }
    if (header->kind != VG_NATIVE_REQUEST || header->status != 0) {
        return VG_NATIVE_BAD_KIND;
    }
    if (header->opcode < VG_NATIVE_INSPECT || header->opcode > VG_NATIVE_CLOSE) {
        return VG_NATIVE_BAD_OPCODE;
    }
    if (header->payload_length != body_size - sizeof(VgNativeFrameHeader)) {
        return VG_NATIVE_BAD_LENGTH;
    }
    expected_id = context->last_request_id == UINT32_MAX ? 1U : context->last_request_id + 1U;
    if (header->request_id == 0 || (context->has_request_id && header->request_id != expected_id)) {
        return VG_NATIVE_BAD_REQUEST_ID;
    }
    *payload = body + sizeof(VgNativeFrameHeader);
    return VG_NATIVE_OK;
}

int bind_vendor_exports(VgNativeWorkerContext *context) {
    if (context == NULL || context->vendor.handle == 0) return 0;
    context->model_get_info = (VgModelGetInfo)vg_platform_library_symbol(&context->vendor, "Model_GetInfo");
    context->model_first_call = (VgModelInstanceCall)vg_platform_library_symbol(&context->vendor, "Model_FirstCall");
    context->model_check_parameters = (VgModelInstanceCall)vg_platform_library_symbol(&context->vendor, "Model_CheckParameters");
    context->model_initialize = (VgModelInstanceCall)vg_platform_library_symbol(&context->vendor, "Model_Initialize");
    context->model_outputs = (VgModelInstanceCall)vg_platform_library_symbol(&context->vendor, "Model_Outputs");
    context->model_iterate = (VgModelInstanceCall)vg_platform_library_symbol(&context->vendor, "Model_Iterate");
    context->model_terminate = (VgModelInstanceCall)vg_platform_library_symbol(&context->vendor, "Model_Terminate");
    context->model_print_info = (VgModelPrintInfo)vg_platform_library_symbol(&context->vendor, "Model_PrintInfo");
    return context->model_get_info != NULL && context->model_first_call != NULL
        && context->model_check_parameters != NULL && context->model_initialize != NULL
        && context->model_outputs != NULL && context->model_iterate != NULL
        && context->model_terminate != NULL && context->model_print_info != NULL;
}

int copy_model_info(VgNativeWorkerContext *context) {
    IEEE_Cigre_DLLInterface_Model_Info *info;
    uint8_t *buffer;
    uint64_t cursor = 0;
    uint64_t limit;
    uint64_t scalar_count = 0;
    int32_t index;
    int group;
    if (context == NULL || context->model_info == NULL) return VG_NATIVE_ABI_FAILURE;
    info = context->model_info;
    if (memcmp(info->DLLInterfaceVersion, "\x01\x01\x00\x00", 4) != 0
            || !isfinite(info->FixedStepBaseSampleTime)
            || info->FixedStepBaseSampleTime <= 0.0
            || info->EMT_RMS_Mode < 1 || info->EMT_RMS_Mode > 3
            || info->NumInputPorts < 0 || (uint32_t)info->NumInputPorts > context->maximum_ports
            || info->NumOutputPorts < 0 || (uint32_t)info->NumOutputPorts > context->maximum_ports
            || info->NumParameters < 0 || (uint32_t)info->NumParameters > context->maximum_parameters
            || info->NumIntStates < 0 || info->NumFloatStates < 0 || info->NumDoubleStates < 0) {
        return VG_NATIVE_ABI_FAILURE;
    }
    if ((uint64_t)info->NumIntStates + (uint64_t)info->NumFloatStates
            + (uint64_t)info->NumDoubleStates > context->maximum_state_scalars) {
        return VG_NATIVE_ABI_FAILURE;
    }
    limit = context->maximum_frame;
    buffer = (uint8_t *)malloc((size_t)limit);
    if (buffer == NULL) return VG_NATIVE_ABI_FAILURE;
    {
        uint8_t interface_record[4] = {1, 0, 0, 0};
        uint8_t sample_record[4] = {1, info->EMT_RMS_Mode, 0, 0};
        VG_APPEND(buffer, cursor, limit, interface_record, 4);
        VG_APPEND(buffer, cursor, limit, info->DLLInterfaceVersion, 4);
        VG_APPEND_TEXT(buffer, cursor, limit, info->ModelName);
        VG_APPEND_TEXT(buffer, cursor, limit, info->ModelVersion);
        VG_APPEND_TEXT(buffer, cursor, limit, info->ModelDescription);
        VG_APPEND_TEXT(buffer, cursor, limit, "");
        VG_APPEND_TEXT(buffer, cursor, limit, info->GeneralInformation);
        VG_APPEND_TEXT(buffer, cursor, limit, info->ModelCreated);
        VG_APPEND_TEXT(buffer, cursor, limit, info->ModelCreator);
        VG_APPEND_TEXT(buffer, cursor, limit, info->ModelLastModifiedDate);
        VG_APPEND_TEXT(buffer, cursor, limit, info->ModelLastModifiedBy);
        VG_APPEND_TEXT(buffer, cursor, limit, info->ModelModifiedComment);
        VG_APPEND_TEXT(buffer, cursor, limit, info->ModelModifiedHistory);
        VG_APPEND_TEXT(buffer, cursor, limit, "");
        VG_APPEND_TEXT(buffer, cursor, limit, "");
        VG_APPEND(buffer, cursor, limit, &info->FixedStepBaseSampleTime, 8);
        VG_APPEND(buffer, cursor, limit, &info->FixedStepBaseSampleTime, 8);
        VG_APPEND(buffer, cursor, limit, sample_record, 4);
    }
    for (group = 0; group < 2; ++group) {
        int32_t count = group == 0 ? info->NumInputPorts : info->NumOutputPorts;
        IEEE_Cigre_DLLInterface_Signal *signals =
            group == 0 ? info->InputPortsInfo : info->OutputPortsInfo;
        if (count > 0 && signals == NULL) {
            free(buffer);
            return VG_NATIVE_ABI_FAILURE;
        }
        VG_APPEND_U32(buffer, cursor, limit, count);
        for (index = 0; index < count; ++index) {
            int signal_type = signals[index].DataType;
            int32_t width = signals[index].Width;
            if (signal_type < 1 || signal_type > 9 || width <= 0
                    || !checked_add_size(scalar_count, (uint64_t)width, &scalar_count)
                    || scalar_count > context->maximum_scalar_slots) {
                free(buffer);
                return VG_NATIVE_ABI_FAILURE;
            }
            VG_APPEND_TEXT(buffer, cursor, limit, signals[index].Name);
            VG_APPEND_TEXT(buffer, cursor, limit, signals[index].Description);
            VG_APPEND_TEXT(buffer, cursor, limit, signals[index].Unit);
            VG_APPEND_TEXT(buffer, cursor, limit, "");
            {
                uint8_t signal_record[4] = {(uint8_t)signal_type, 0, 0, 0};
                VG_APPEND(buffer, cursor, limit, signal_record, 4);
            }
            VG_APPEND_U32(buffer, cursor, limit, width);
            VG_APPEND_U32(buffer, cursor, limit, 0);
        }
    }
    if (info->NumParameters > 0 && info->ParametersInfo == NULL) {
        free(buffer);
        return VG_NATIVE_ABI_FAILURE;
    }
    VG_APPEND_U32(buffer, cursor, limit, info->NumParameters);
    for (index = 0; index < info->NumParameters; ++index) {
        IEEE_Cigre_DLLInterface_Parameter *parameter = &info->ParametersInfo[index];
        uint8_t tag = (uint8_t)parameter->DataType;
        uint8_t fixed = (uint8_t)parameter->FixedValue;
        uint8_t reserved[2] = {0, 0};
        uint8_t bounds[4];
        if (tag < 1 || tag > 10 || (fixed != 0 && fixed != 1)) {
            free(buffer);
            return VG_NATIVE_ABI_FAILURE;
        }
        VG_APPEND_TEXT(buffer, cursor, limit, parameter->Name);
        VG_APPEND_TEXT(buffer, cursor, limit, parameter->GroupName);
        VG_APPEND_TEXT(buffer, cursor, limit, parameter->Description);
        VG_APPEND_TEXT(buffer, cursor, limit, parameter->Unit);
        VG_APPEND(buffer, cursor, limit, &tag, 1);
        VG_APPEND(buffer, cursor, limit, &fixed, 1);
        VG_APPEND(buffer, cursor, limit, reserved, 2);
        VG_APPEND(buffer, cursor, limit, &tag, 1);
        if (tag == 1) VG_APPEND(buffer, cursor, limit, &parameter->DefaultValue.Char_Val, 1);
        else if (tag == 2) VG_APPEND(buffer, cursor, limit, &parameter->DefaultValue.Int8_Val, 1);
        else if (tag == 3) VG_APPEND(buffer, cursor, limit, &parameter->DefaultValue.Uint8_Val, 1);
        else if (tag == 4) VG_APPEND(buffer, cursor, limit, &parameter->DefaultValue.Int16_Val, 2);
        else if (tag == 5) VG_APPEND(buffer, cursor, limit, &parameter->DefaultValue.Uint16_Val, 2);
        else if (tag == 6) VG_APPEND(buffer, cursor, limit, &parameter->DefaultValue.Int32_Val, 4);
        else if (tag == 7) VG_APPEND(buffer, cursor, limit, &parameter->DefaultValue.Uint32_Val, 4);
        else if (tag == 8) VG_APPEND(buffer, cursor, limit, &parameter->DefaultValue.Real32_Val, 4);
        else if (tag == 9) VG_APPEND(buffer, cursor, limit, &parameter->DefaultValue.Real64_Val, 8);
        else VG_APPEND_TEXT(buffer, cursor, limit, parameter->DefaultValue.Char_Ptr);
        bounds[0] = tag == 10 ? 0 : 1;
        bounds[1] = tag == 10 ? 0 : 1;
        bounds[2] = 0;
        bounds[3] = 0;
        VG_APPEND(buffer, cursor, limit, bounds, 4);
        if (tag != 10) {
            VG_APPEND(buffer, cursor, limit, &tag, 1);
            if (tag == 1) VG_APPEND(buffer, cursor, limit, &parameter->MinValue.Char_Val, 1);
            else if (tag == 2) VG_APPEND(buffer, cursor, limit, &parameter->MinValue.Int8_Val, 1);
            else if (tag == 3) VG_APPEND(buffer, cursor, limit, &parameter->MinValue.Uint8_Val, 1);
            else if (tag == 4) VG_APPEND(buffer, cursor, limit, &parameter->MinValue.Int16_Val, 2);
            else if (tag == 5) VG_APPEND(buffer, cursor, limit, &parameter->MinValue.Uint16_Val, 2);
            else if (tag == 6) VG_APPEND(buffer, cursor, limit, &parameter->MinValue.Int32_Val, 4);
            else if (tag == 7) VG_APPEND(buffer, cursor, limit, &parameter->MinValue.Uint32_Val, 4);
            else if (tag == 8) VG_APPEND(buffer, cursor, limit, &parameter->MinValue.Real32_Val, 4);
            else VG_APPEND(buffer, cursor, limit, &parameter->MinValue.Real64_Val, 8);
            VG_APPEND(buffer, cursor, limit, &tag, 1);
            if (tag == 1) VG_APPEND(buffer, cursor, limit, &parameter->MaxValue.Char_Val, 1);
            else if (tag == 2) VG_APPEND(buffer, cursor, limit, &parameter->MaxValue.Int8_Val, 1);
            else if (tag == 3) VG_APPEND(buffer, cursor, limit, &parameter->MaxValue.Uint8_Val, 1);
            else if (tag == 4) VG_APPEND(buffer, cursor, limit, &parameter->MaxValue.Int16_Val, 2);
            else if (tag == 5) VG_APPEND(buffer, cursor, limit, &parameter->MaxValue.Uint16_Val, 2);
            else if (tag == 6) VG_APPEND(buffer, cursor, limit, &parameter->MaxValue.Int32_Val, 4);
            else if (tag == 7) VG_APPEND(buffer, cursor, limit, &parameter->MaxValue.Uint32_Val, 4);
            else if (tag == 8) VG_APPEND(buffer, cursor, limit, &parameter->MaxValue.Real32_Val, 4);
            else VG_APPEND(buffer, cursor, limit, &parameter->MaxValue.Real64_Val, 8);
        }
    }
    VG_APPEND_U32(buffer, cursor, limit, 0);
    VG_APPEND_U32(buffer, cursor, limit, 0);
    VG_APPEND_U32(buffer, cursor, limit, info->NumIntStates);
    VG_APPEND_U32(buffer, cursor, limit, info->NumFloatStates);
    VG_APPEND_U32(buffer, cursor, limit, info->NumDoubleStates);
    if (!hash_bytes(buffer, cursor, context->raw_model_sha256)) {
        free(buffer);
        return VG_NATIVE_ABI_FAILURE;
    }
    context->raw_model_info = buffer;
    context->raw_model_info_size = cursor;
    return VG_NATIVE_OK;
}


VgNativeStatus handle_inspect(VgNativeWorkerContext *context, const uint8_t *payload,
                           uint64_t payload_size, uint8_t **response, uint64_t *response_size) {
    const uint8_t *cursor = payload;
    uint64_t remaining = payload_size;
    uint8_t interface_record[4];
    uint32_t path_size;
    uint32_t system_path_size;
    uint64_t system_volume;
    uint8_t system_id[16];
    uint8_t expected_hash[32];
    uint8_t actual_hash[32];
    uint8_t self_hash[32];
    uint64_t expected_size;
    VgPlatformFileIdentity expected_system_identity;
    uint8_t *out;
    uint64_t out_cursor = 0;
    uint8_t flags[8] = {1, 0, 0, 0, 0, 0, 0, 0};
    if (context->state != VG_NATIVE_CREATED) return VG_NATIVE_BAD_STATE;
    VG_REQUIRE(remaining, 4);
    memcpy(interface_record, cursor, 4);
    cursor += 4;
    remaining -= 4;
    if (interface_record[0] < 1 || interface_record[0] > 3
            || interface_record[1] != 0 || interface_record[2] != 0 || interface_record[3] != 0) {
        return VG_NATIVE_BAD_PAYLOAD;
    }
    context->interface_kind = interface_record[0];

    VG_READ_U32(cursor, remaining, path_size);
    VG_REQUIRE(remaining, path_size);
    if (path_size == 0 || path_size >= sizeof(context->staged_path)
            || memchr(cursor, 0, path_size) != NULL) return VG_NATIVE_BAD_PAYLOAD;
    memcpy(context->staged_path, cursor, path_size);
    context->staged_path[path_size] = '\0';
    cursor += path_size;
    remaining -= path_size;
    VG_READ_U64(cursor, remaining, expected_size);
    VG_REQUIRE(remaining, 32);
    memcpy(expected_hash, cursor, 32);
    cursor += 32;
    remaining -= 32;
    VG_READ_U64(cursor, remaining, system_volume);
    VG_REQUIRE(remaining, 16);
    memcpy(system_id, cursor, 16);
    cursor += 16;
    remaining -= 16;
    VG_READ_U32(cursor, remaining, system_path_size);
    VG_REQUIRE(remaining, system_path_size);
    if (system_path_size >= sizeof(context->system_path)
            || memchr(cursor, 0, system_path_size) != NULL) return VG_NATIVE_BAD_PAYLOAD;
    memcpy(context->system_path, cursor, system_path_size);
    context->system_path[system_path_size] = '\0';
    cursor += system_path_size;
    remaining -= system_path_size;
    VG_REQUIRE(remaining, 84);
    memcpy(&context->maximum_binary, cursor, 8); cursor += 8;
    memcpy(&context->maximum_frame, cursor, 8); cursor += 8;
    memcpy(&context->maximum_instances, cursor, 4); cursor += 4;
    memcpy(&context->maximum_ports, cursor, 4); cursor += 4;
    memcpy(&context->maximum_parameters, cursor, 4); cursor += 4;
    memcpy(&context->maximum_scalar_slots, cursor, 8); cursor += 8;
    memcpy(&context->maximum_state_scalars, cursor, 8); cursor += 8;
    memcpy(&context->maximum_instance_bytes, cursor, 8); cursor += 8;
    memcpy(&context->maximum_worker_bytes, cursor, 8); cursor += 8;
    memcpy(&context->maximum_metadata_text, cursor, 8); cursor += 8;
    memcpy(&context->maximum_capture, cursor, 8); cursor += 8;
    memcpy(&context->maximum_observations, cursor, 8); cursor += 8;
    remaining -= 84;
    if (remaining != 0 || expected_size == 0 || expected_size > context->maximum_binary
            || context->maximum_frame < sizeof(VgNativeFrameHeader)
            || context->maximum_instances == 0 || context->maximum_ports == 0
            || context->maximum_parameters == 0 || context->maximum_scalar_slots == 0
            || context->maximum_state_scalars == 0 || context->maximum_instance_bytes == 0
            || context->maximum_worker_bytes == 0 || context->maximum_metadata_text == 0
            || context->maximum_capture == 0
            || context->maximum_capture > context->maximum_frame
            || context->maximum_observations == 0) {
        return VG_NATIVE_BAD_PAYLOAD;
    }
    if (context->interface_kind == 1) {
        context->instances = (VgNativeInstance **)calloc(
            context->maximum_instances,
            sizeof(VgNativeInstance *)
        );
        if (context->instances == NULL) return VG_NATIVE_ABI_FAILURE;
    } else {
        context->instances = NULL;
    }
    if (!vg_platform_capture_open(&context->capture)) return VG_NATIVE_ABI_FAILURE;
    expected_system_identity.device_identifier = system_volume;
    memcpy(expected_system_identity.file_identifier, system_id, 16);
    if (!vg_platform_module_guard_begin(
            &context->module_guard, context->maximum_observations,
            context->system_path, &expected_system_identity
    )) return VG_NATIVE_CONTENT_IDENTITY_FAILURE;
    if (!vg_platform_verify_file(context->staged_path, expected_size, expected_hash,
                                 actual_hash, &context->staged_file)) {
        return VG_NATIVE_CONTENT_IDENTITY_FAILURE;
    }
    context->staged_size = expected_size;
    memcpy(context->staged_sha256, actual_hash, 32);
    if (!vg_platform_library_open(context->staged_path, &context->staged_file,
                                  &context->vendor)) return VG_NATIVE_ABI_FAILURE;
    if (!vg_platform_module_guard_validate(
            &context->module_guard, &context->staged_file, context->system_path
    )) return VG_NATIVE_DEPENDENCY_FAILURE;
    if (context->interface_kind == 1) {
        if (!bind_vendor_exports(context)) return VG_NATIVE_ABI_FAILURE;
        context->model_info = context->model_get_info();
        if (context->model_info == NULL) return VG_NATIVE_ABI_FAILURE;
        {
            int info_status = copy_model_info(context);
            if (info_status != VG_NATIVE_OK) return (VgNativeStatus)info_status;
        }
    } else {
        VgNativeAdapterLimits limits;
        int adapter_status;
        limits.maximum_instances = context->maximum_instances;
        limits.maximum_ports = context->maximum_ports;
        limits.maximum_parameters = context->maximum_parameters;
        limits.maximum_scalar_slots = context->maximum_scalar_slots;
        limits.maximum_state_scalars = context->maximum_state_scalars;
        limits.maximum_instance_bytes = context->maximum_instance_bytes;
        limits.maximum_frame_bytes = context->maximum_frame;
        if (context->interface_kind == 2) {
            adapter_status = vg_ieee_cigre_v1_0_bind(&context->vendor, &limits, &context->ieee_cigre_v1_0);
            if (adapter_status == VG_NATIVE_OK) adapter_status = vg_ieee_cigre_v1_0_copy_model_info(&context->ieee_cigre_v1_0, &context->raw_model_info, &context->raw_model_info_size);
        } else {
            adapter_status = vg_iec_ese_bind(&context->vendor, &limits, &context->iec_ese);
            if (adapter_status == VG_NATIVE_OK) adapter_status = vg_iec_ese_copy_model_info(&context->iec_ese, &context->raw_model_info, &context->raw_model_info_size);
        }
        if (adapter_status != VG_NATIVE_OK) return (VgNativeStatus)adapter_status;
        if (!hash_bytes(
                context->raw_model_info, context->raw_model_info_size,
                context->raw_model_sha256
        )) return VG_NATIVE_ABI_FAILURE;
    }
    if (!vg_platform_executable_hash(self_hash)) {
        return VG_NATIVE_CONTENT_IDENTITY_FAILURE;
    }
    memcpy(context->worker_sha256, self_hash, 32);
    out = (uint8_t *)malloc((size_t)context->maximum_frame);
    if (out == NULL) return VG_NATIVE_ABI_FAILURE;
    VG_APPEND(out, out_cursor, context->maximum_frame, context->worker_sha256, 32);
    VG_APPEND_U64(out, out_cursor, context->maximum_frame, context->maximum_observations);
    VG_APPEND(out, out_cursor, context->maximum_frame, flags, 8);
    VG_APPEND_U32(out, out_cursor, context->maximum_frame, 1);
    VG_APPEND_TEXT(
        out, out_cursor, context->maximum_frame, vg_platform_runtime_library_name()
    );
    VG_APPEND(out, out_cursor, context->maximum_frame, context->raw_model_info,
              context->raw_model_info_size);
    context->state = VG_NATIVE_INSPECTED;
    *response = out;
    *response_size = out_cursor;
    return VG_NATIVE_OK;
}

void normalize_capture_text(uint8_t *bytes, uint64_t *size) {
    uint64_t source_index;
    uint64_t target_index;
    if (bytes == NULL || size == NULL) {
        return;
    } else {
        source_index = 0;
        target_index = 0;
    }
    while (source_index < *size) {
        if (bytes[source_index] != '\r') {
            bytes[target_index] = bytes[source_index];
            target_index += 1;
        } else {
            /* Carriage returns are omitted for platform-neutral diagnostics. */
        }
        source_index += 1;
    }
    *size = target_index;
}

int capture_print_info(VgNativeWorkerContext *context, int32_t *return_code,
                       uint8_t **stdout_bytes, uint64_t *stdout_size,
                       uint8_t **stderr_bytes, uint64_t *stderr_size,
                       uint8_t *stdout_truncated, uint8_t *stderr_truncated) {
    int captured;
    if (context == NULL || return_code == NULL || stdout_bytes == NULL || stderr_bytes == NULL
            || stdout_size == NULL || stderr_size == NULL || stdout_truncated == NULL
            || stderr_truncated == NULL) {
        return 0;
    } else if (context->interface_kind == 1) {
        *return_code = context->model_print_info();
    } else if (context->interface_kind == 2) {
        *return_code = vg_ieee_cigre_v1_0_print_info(&context->ieee_cigre_v1_0);
    } else {
        *return_code = vg_iec_ese_print_info(&context->iec_ese);
    }
    captured = vg_platform_capture_finish(
        &context->capture, context->maximum_capture,
        stdout_bytes, stdout_size, stderr_bytes, stderr_size,
        stdout_truncated, stderr_truncated
    );
    if (captured) {
        normalize_capture_text(*stdout_bytes, stdout_size);
        normalize_capture_text(*stderr_bytes, stderr_size);
    } else {
        captured = 0;
    }
    return captured;
}
VgNativeStatus handle_prepare(VgNativeWorkerContext *context, const uint8_t *payload,
                           uint64_t payload_size, uint8_t **response, uint64_t *response_size) {
    int32_t code;
    uint8_t *stdout_bytes = NULL;
    uint8_t *stderr_bytes = NULL;
    uint64_t stdout_size = 0;
    uint64_t stderr_size = 0;
    uint8_t stdout_truncated = 0;
    uint8_t stderr_truncated = 0;
    uint8_t *out;
    uint64_t cursor = 0;
    uint8_t flags[4];
    if (context->state != VG_NATIVE_INSPECTED) return VG_NATIVE_BAD_STATE;
    if (payload_size != 64 || memcmp(payload, context->raw_model_sha256, 32) != 0) {
        return VG_NATIVE_CONTENT_IDENTITY_FAILURE;
    }
    if (!vg_platform_module_guard_validate(
            &context->module_guard, &context->staged_file, context->system_path
    )) return VG_NATIVE_DEPENDENCY_FAILURE;
    if (!capture_print_info(context, &code, &stdout_bytes, &stdout_size,
                            &stderr_bytes, &stderr_size,
                            &stdout_truncated, &stderr_truncated)) {
        return VG_NATIVE_ABI_FAILURE;
    }
    out = (uint8_t *)malloc((size_t)context->maximum_frame);
    if (out == NULL) {
        free(stdout_bytes);
        free(stderr_bytes);
        return VG_NATIVE_ABI_FAILURE;
    }
    VG_APPEND(out, cursor, context->maximum_frame, &code, 4);
    VG_APPEND_U64(out, cursor, context->maximum_frame, stdout_size);
    VG_APPEND(out, cursor, context->maximum_frame, stdout_bytes, stdout_size);
    VG_APPEND_U64(out, cursor, context->maximum_frame, stderr_size);
    VG_APPEND(out, cursor, context->maximum_frame, stderr_bytes, stderr_size);
    flags[0] = stdout_truncated;
    flags[1] = stderr_truncated;
    flags[2] = 0;
    flags[3] = 0;
    VG_APPEND(out, cursor, context->maximum_frame, flags, 4);
    free(stdout_bytes);
    free(stderr_bytes);
    context->state = VG_NATIVE_PREPARED;
    *response = out;
    *response_size = cursor;
    return VG_NATIVE_OK;
}


VgNativeStatus create_instance(VgNativeWorkerContext *context, const uint8_t **payload_cursor,
                            uint64_t *payload_remaining, VgNativeInstance **created) {
    const uint8_t *cursor;
    uint64_t remaining;
    uint32_t identifier_size;
    uint8_t mode;
    uint32_t input_count;
    uint32_t override_count;
    VgNativeInstance *instance;
    IEEE_Cigre_DLLInterface_Model_Info *info;
    uint64_t input_size = 0;
    uint64_t output_size = 0;
    uint64_t parameter_size = 0;
    uint32_t flat;
    int32_t port;
    int32_t element;
    int32_t parameter_index;
    if (context == NULL || payload_cursor == NULL || payload_remaining == NULL || created == NULL) {
        return VG_NATIVE_BAD_PAYLOAD;
    }
    cursor = *payload_cursor;
    remaining = *payload_remaining;
    info = context->model_info;
    instance = (VgNativeInstance *)calloc(1, sizeof(VgNativeInstance));
    if (instance == NULL) return VG_NATIVE_ABI_FAILURE;
    VG_READ_U32(cursor, remaining, identifier_size);
    VG_REQUIRE(remaining, identifier_size);
    if (identifier_size == 0 || memchr(cursor, 0, identifier_size) != NULL) {
        free(instance);
        return VG_NATIVE_BAD_PAYLOAD;
    }
    instance->identifier = (char *)malloc(identifier_size + 1);
    if (instance->identifier == NULL) {
        free(instance);
        return VG_NATIVE_ABI_FAILURE;
    }
    memcpy(instance->identifier, cursor, identifier_size);
    instance->identifier[identifier_size] = 0;
    cursor += identifier_size;
    remaining -= identifier_size;
    VG_REQUIRE(remaining, 4);
    mode = cursor[0];
    if ((mode != 1 && mode != 2) || cursor[1] != 0 || cursor[2] != 0 || cursor[3] != 0
            || (info->EMT_RMS_Mode != 3 && info->EMT_RMS_Mode != mode)) {
        destroy_instance(instance);
        return VG_NATIVE_BAD_PAYLOAD;
    }
    cursor += 4;
    remaining -= 4;
    for (port = 0; port < info->NumInputPorts; ++port) {
        instance->input_count += (uint32_t)info->InputPortsInfo[port].Width;
    }
    for (port = 0; port < info->NumOutputPorts; ++port) {
        instance->output_count += (uint32_t)info->OutputPortsInfo[port].Width;
    }
    instance->input_offsets = (uint32_t *)calloc(instance->input_count == 0 ? 1 : instance->input_count, 4);
    instance->input_types = (uint8_t *)calloc(instance->input_count == 0 ? 1 : instance->input_count, 1);
    instance->output_offsets = (uint32_t *)calloc(instance->output_count == 0 ? 1 : instance->output_count, 4);
    instance->output_types = (uint8_t *)calloc(instance->output_count == 0 ? 1 : instance->output_count, 1);
    instance->parameter_offsets = (uint32_t *)calloc(info->NumParameters == 0 ? 1 : info->NumParameters, 4);
    if (instance->input_offsets == NULL || instance->input_types == NULL
            || instance->output_offsets == NULL || instance->output_types == NULL
            || instance->parameter_offsets == NULL) {
        destroy_instance(instance);
        return VG_NATIVE_ABI_FAILURE;
    }
    flat = 0;
    for (port = 0; port < info->NumInputPorts; ++port) {
        uint32_t type = (uint32_t)info->InputPortsInfo[port].DataType;
        uint32_t size = type <= 3 ? 1 : (type <= 5 ? 2 : (type <= 8 ? 4 : 8));
        input_size = (input_size + size - 1) & ~((uint64_t)size - 1);
        for (element = 0; element < info->InputPortsInfo[port].Width; ++element) {
            instance->input_offsets[flat] = (uint32_t)(input_size + (uint64_t)element * size);
            instance->input_types[flat] = (uint8_t)type;
            ++flat;
        }
        input_size += (uint64_t)info->InputPortsInfo[port].Width * size;
    }
    flat = 0;
    for (port = 0; port < info->NumOutputPorts; ++port) {
        uint32_t type = (uint32_t)info->OutputPortsInfo[port].DataType;
        uint32_t size = type <= 3 ? 1 : (type <= 5 ? 2 : (type <= 8 ? 4 : 8));
        output_size = (output_size + size - 1) & ~((uint64_t)size - 1);
        for (element = 0; element < info->OutputPortsInfo[port].Width; ++element) {
            instance->output_offsets[flat] = (uint32_t)(output_size + (uint64_t)element * size);
            instance->output_types[flat] = (uint8_t)type;
            ++flat;
        }
        output_size += (uint64_t)info->OutputPortsInfo[port].Width * size;
    }
    for (parameter_index = 0; parameter_index < info->NumParameters; ++parameter_index) {
        uint32_t type = (uint32_t)info->ParametersInfo[parameter_index].DataType;
        uint32_t size = type <= 3 ? 1 : (type <= 5 ? 2 : (type <= 8 ? 4 : (type == 9 ? 8 : (uint32_t)sizeof(char *))));
        parameter_size = (parameter_size + size - 1) & ~((uint64_t)size - 1);
        instance->parameter_offsets[parameter_index] = (uint32_t)parameter_size;
        parameter_size += size;
    }
    if (input_size + output_size + parameter_size > context->maximum_instance_bytes) {
        destroy_instance(instance);
        return VG_NATIVE_BAD_PAYLOAD;
    }
    instance->inputs = (uint8_t *)calloc((size_t)(input_size == 0 ? 1 : input_size), 1);
    instance->outputs = (uint8_t *)calloc((size_t)(output_size == 0 ? 1 : output_size), 1);
    instance->parameters = (uint8_t *)calloc((size_t)(parameter_size == 0 ? 1 : parameter_size), 1);
    instance->strings = (char **)calloc(info->NumParameters == 0 ? 1 : info->NumParameters, sizeof(char *));
    instance->abi.IntStates = (int32_t *)calloc(info->NumIntStates == 0 ? 1 : info->NumIntStates, sizeof(int32_t));
    instance->abi.FloatStates = (float *)calloc(info->NumFloatStates == 0 ? 1 : info->NumFloatStates, sizeof(float));
    instance->abi.DoubleStates = (double *)calloc(info->NumDoubleStates == 0 ? 1 : info->NumDoubleStates, sizeof(double));
    if (instance->inputs == NULL || instance->outputs == NULL || instance->parameters == NULL
            || instance->strings == NULL || instance->abi.IntStates == NULL
            || instance->abi.FloatStates == NULL || instance->abi.DoubleStates == NULL) {
        destroy_instance(instance);
        return VG_NATIVE_ABI_FAILURE;
    }
    instance->abi.ExternalInputs = instance->inputs;
    instance->abi.ExternalOutputs = instance->outputs;
    instance->abi.Parameters = instance->parameters;
    instance->abi.Time = 0.0;
    instance->abi.SimTool_EMT_RMS_Mode = mode;
    for (parameter_index = 0; parameter_index < info->NumParameters; ++parameter_index) {
        IEEE_Cigre_DLLInterface_Parameter *parameter = &info->ParametersInfo[parameter_index];
        uint8_t type = (uint8_t)parameter->DataType;
        uint8_t *destination = instance->parameters + instance->parameter_offsets[parameter_index];
        if (type == 1) memcpy(destination, &parameter->DefaultValue.Char_Val, 1);
        else if (type == 2) memcpy(destination, &parameter->DefaultValue.Int8_Val, 1);
        else if (type == 3) memcpy(destination, &parameter->DefaultValue.Uint8_Val, 1);
        else if (type == 4) memcpy(destination, &parameter->DefaultValue.Int16_Val, 2);
        else if (type == 5) memcpy(destination, &parameter->DefaultValue.Uint16_Val, 2);
        else if (type == 6) memcpy(destination, &parameter->DefaultValue.Int32_Val, 4);
        else if (type == 7) memcpy(destination, &parameter->DefaultValue.Uint32_Val, 4);
        else if (type == 8) memcpy(destination, &parameter->DefaultValue.Real32_Val, 4);
        else if (type == 9) memcpy(destination, &parameter->DefaultValue.Real64_Val, 8);
        else {
            uint64_t text_size = 0;
            const char *source_text = parameter->DefaultValue.Char_Ptr == NULL
                ? "" : parameter->DefaultValue.Char_Ptr;
            if (!vg_native_bounded_text_size(source_text, 16384U, &text_size)) {
                destroy_instance(instance);
                return VG_NATIVE_ABI_FAILURE;
            }
            instance->strings[instance->string_count] = (char *)malloc(text_size + 1);
            if (instance->strings[instance->string_count] == NULL) {
                destroy_instance(instance);
                return VG_NATIVE_ABI_FAILURE;
            }
            memcpy(instance->strings[instance->string_count],
                   parameter->DefaultValue.Char_Ptr == NULL ? "" : parameter->DefaultValue.Char_Ptr,
                   text_size);
            instance->strings[instance->string_count][text_size] = 0;
            memcpy(destination, &instance->strings[instance->string_count], sizeof(char *));
            instance->string_count += 1;
        }
    }
    VG_READ_U32(cursor, remaining, input_count);
    if (input_count != instance->input_count) {
        destroy_instance(instance);
        return VG_NATIVE_BAD_PAYLOAD;
    }
    for (flat = 0; flat < input_count; ++flat) {
        uint8_t type;
        uint32_t size;
        VG_REQUIRE(remaining, 1);
        type = *cursor++;
        remaining -= 1;
        if (type != instance->input_types[flat] || type < 1 || type > 9) {
            destroy_instance(instance);
            return VG_NATIVE_BAD_PAYLOAD;
        }
        size = type <= 3 ? 1 : (type <= 5 ? 2 : (type <= 8 ? 4 : 8));
        VG_REQUIRE(remaining, size);
        memcpy(instance->inputs + instance->input_offsets[flat], cursor, size);
        cursor += size;
        remaining -= size;
    }
    VG_READ_U32(cursor, remaining, override_count);
    for (flat = 0; flat < override_count; ++flat) {
        uint32_t ordinal;
        uint8_t type;
        uint8_t fixed;
        uint32_t size;
        VG_READ_U32(cursor, remaining, ordinal);
        VG_REQUIRE(remaining, 5);
        type = cursor[0];
        fixed = cursor[1];
        if (cursor[2] != 0 || cursor[3] != 0 || cursor[4] != type
                || ordinal >= (uint32_t)info->NumParameters
                || type != (uint8_t)info->ParametersInfo[ordinal].DataType
                || fixed != (uint8_t)info->ParametersInfo[ordinal].FixedValue) {
            destroy_instance(instance);
            return VG_NATIVE_BAD_PAYLOAD;
        }
        cursor += 5;
        remaining -= 5;
        if (type == 10) {
            uint32_t text_size;
            VG_READ_U32(cursor, remaining, text_size);
            VG_REQUIRE(remaining, text_size);
            if (text_size > 16384 || memchr(cursor, 0, text_size) != NULL) {
                destroy_instance(instance);
                return VG_NATIVE_BAD_PAYLOAD;
            }
            instance->strings[instance->string_count] = (char *)malloc(text_size + 1);
            if (instance->strings[instance->string_count] == NULL) {
                destroy_instance(instance);
                return VG_NATIVE_ABI_FAILURE;
            }
            memcpy(instance->strings[instance->string_count], cursor, text_size);
            instance->strings[instance->string_count][text_size] = 0;
            memcpy(instance->parameters + instance->parameter_offsets[ordinal],
                   &instance->strings[instance->string_count], sizeof(char *));
            instance->string_count += 1;
            cursor += text_size;
            remaining -= text_size;
        } else {
            size = type <= 3 ? 1 : (type <= 5 ? 2 : (type <= 8 ? 4 : 8));
            VG_REQUIRE(remaining, size);
            memcpy(instance->parameters + instance->parameter_offsets[ordinal], cursor, size);
            cursor += size;
            remaining -= size;
        }
    }
    *payload_cursor = cursor;
    *payload_remaining = remaining;
    *created = instance;
    return VG_NATIVE_OK;
}

void destroy_instance(VgNativeInstance *instance) {
    uint32_t index;
    if (instance == NULL) return;
    for (index = 0; index < instance->string_count; ++index) free(instance->strings[index]);
    free(instance->strings);
    free(instance->identifier);
    free(instance->inputs);
    free(instance->outputs);
    free(instance->parameters);
    free(instance->input_offsets);
    free(instance->input_types);
    free(instance->output_offsets);
    free(instance->output_types);
    free(instance->parameter_offsets);
    free(instance->abi.IntStates);
    free(instance->abi.FloatStates);
    free(instance->abi.DoubleStates);
    free(instance);
}

VgNativeStatus call_instance_function(VgNativeWorkerContext *context, VgNativeInstance *instance,
                                     VgModelInstanceCall function, VgNativeCallOperation operation,
                                     uint8_t *response, uint64_t *cursor, uint64_t limit) {
    int32_t code;
    uint8_t prefix[4];
    if (context == NULL || instance == NULL || function == NULL || response == NULL || cursor == NULL) {
        return VG_NATIVE_BAD_PAYLOAD;
    }
    if (!vg_platform_module_guard_validate(
            &context->module_guard, &context->staged_file, context->system_path
    )) return VG_NATIVE_DEPENDENCY_FAILURE;
    code = function(&instance->abi);
    prefix[0] = (uint8_t)operation;
    prefix[1] = 0;
    prefix[2] = 0;
    prefix[3] = 0;
    VG_APPEND(response, *cursor, limit, prefix, 4);
    VG_APPEND(response, *cursor, limit, &code, 4);
    VG_APPEND_TEXT(response, *cursor, limit, instance->abi.LastErrorMessage);
    VG_APPEND_TEXT(response, *cursor, limit, instance->abi.LastGeneralMessage);
    return VG_NATIVE_OK;
}

VgNativeStatus handle_initialize(VgNativeWorkerContext *context, const uint8_t *payload,
                              uint64_t payload_size, uint8_t **response, uint64_t *response_size) {
    const uint8_t *input = payload;
    uint64_t remaining = payload_size;
    uint32_t count;
    uint32_t index;
    uint8_t *out;
    uint64_t out_cursor = 0;
    if (context->state != VG_NATIVE_PREPARED && context->state != VG_NATIVE_ACTIVE) {
        return VG_NATIVE_BAD_STATE;
    }
    VG_READ_U32(input, remaining, count);
    if (count == 0 || count > context->maximum_instances
            || context->instance_count + count > context->maximum_instances) {
        return VG_NATIVE_BAD_PAYLOAD;
    }
    out = (uint8_t *)malloc((size_t)context->maximum_frame);
    if (out == NULL) return VG_NATIVE_ABI_FAILURE;
    VG_APPEND_U32(out, out_cursor, context->maximum_frame, count);
    for (index = 0; index < count; ++index) {
        VgNativeInstance *instance = NULL;
        VgNativeStatus status = create_instance(context, &input, &remaining, &instance);
        uint32_t id_size;
        uint32_t output_index;
        if (status != VG_NATIVE_OK) {
            free(out);
            return status;
        }
        if (context->instance_count > 0
                && strcmp(context->instances[context->instance_count - 1]->identifier,
                          instance->identifier) >= 0) {
            destroy_instance(instance);
            free(out);
            return VG_NATIVE_BAD_PAYLOAD;
        }
        context->instances[context->instance_count++] = instance;
        id_size = (uint32_t)strlen(instance->identifier);
        VG_APPEND_U32(out, out_cursor, context->maximum_frame, id_size);
        VG_APPEND(out, out_cursor, context->maximum_frame, instance->identifier, id_size);
        VG_APPEND_U32(out, out_cursor, context->maximum_frame, 4);
        status = call_instance_function(
            context, instance, context->model_first_call,
            VG_NATIVE_FIRST_CALL, out, &out_cursor, context->maximum_frame
        );
        if (status == VG_NATIVE_OK) {
            status = call_instance_function(
                context, instance, context->model_check_parameters,
                VG_NATIVE_CHECK_PARAMETERS, out, &out_cursor, context->maximum_frame
            );
        }
        if (status == VG_NATIVE_OK) {
            status = call_instance_function(
                context, instance, context->model_initialize,
                VG_NATIVE_INITIALIZE_CALL, out, &out_cursor, context->maximum_frame
            );
        }
        if (status == VG_NATIVE_OK) {
            status = call_instance_function(
                context, instance, context->model_outputs,
                VG_NATIVE_OUTPUTS, out, &out_cursor, context->maximum_frame
            );
        }
        if (status != VG_NATIVE_OK) {
            free(out);
            return status;
        }
        instance->started = 1;
        VG_APPEND_U32(out, out_cursor, context->maximum_frame, instance->output_count);
        for (output_index = 0; output_index < instance->output_count; ++output_index) {
            uint8_t type = instance->output_types[output_index];
            uint32_t size = type <= 3 ? 1 : (type <= 5 ? 2 : (type <= 8 ? 4 : 8));
            VG_APPEND(out, out_cursor, context->maximum_frame, &type, 1);
            VG_APPEND(out, out_cursor, context->maximum_frame,
                      instance->outputs + instance->output_offsets[output_index], size);
        }
    }
    if (remaining != 0) {
        free(out);
        return VG_NATIVE_BAD_PAYLOAD;
    }
    context->state = VG_NATIVE_ACTIVE;
    *response = out;
    *response_size = out_cursor;
    return VG_NATIVE_OK;
}


VgNativeStatus handle_sample(VgNativeWorkerContext *context, const uint8_t *payload,
                          uint64_t payload_size, uint8_t **response, uint64_t *response_size) {
    const uint8_t *input = payload;
    uint64_t remaining = payload_size;
    double sample_time;
    uint32_t count;
    uint32_t row_index;
    uint8_t *out;
    uint64_t out_cursor = 0;
    char previous_id[4096];
    previous_id[0] = 0;
    if (context->state != VG_NATIVE_ACTIVE) return VG_NATIVE_BAD_STATE;
    VG_REQUIRE(remaining, 8);
    memcpy(&sample_time, input, 8);
    input += 8;
    remaining -= 8;
    if (!isfinite(sample_time) || sample_time <= 0.0) return VG_NATIVE_BAD_PAYLOAD;
    VG_READ_U32(input, remaining, count);
    if (count == 0 || count > context->instance_count) return VG_NATIVE_BAD_PAYLOAD;
    out = (uint8_t *)malloc((size_t)context->maximum_frame);
    if (out == NULL) return VG_NATIVE_ABI_FAILURE;
    VG_APPEND_U32(out, out_cursor, context->maximum_frame, count);
    for (row_index = 0; row_index < count; ++row_index) {
        uint32_t id_size;
        char identifier[4096];
        uint32_t instance_index;
        VgNativeInstance *instance = NULL;
        uint32_t input_count;
        uint32_t value_index;
        VG_READ_U32(input, remaining, id_size);
        VG_REQUIRE(remaining, id_size);
        if (id_size == 0 || id_size >= sizeof(identifier) || memchr(input, 0, id_size) != NULL) {
            free(out);
            return VG_NATIVE_BAD_PAYLOAD;
        }
        memcpy(identifier, input, id_size);
        identifier[id_size] = 0;
        input += id_size;
        remaining -= id_size;
        if (strcmp(previous_id, identifier) >= 0) {
            free(out);
            return VG_NATIVE_BAD_PAYLOAD;
        }
        memcpy(previous_id, identifier, id_size + 1);
        for (instance_index = 0; instance_index < context->instance_count; ++instance_index) {
            if (strcmp(context->instances[instance_index]->identifier, identifier) == 0) {
                instance = context->instances[instance_index];
                break;
            }
        }
        if (instance == NULL || !instance->started || instance->terminated) {
            free(out);
            return VG_NATIVE_BAD_PAYLOAD;
        }
        VG_READ_U32(input, remaining, input_count);
        if (input_count != instance->input_count) {
            free(out);
            return VG_NATIVE_BAD_PAYLOAD;
        }
        for (value_index = 0; value_index < input_count; ++value_index) {
            uint8_t type;
            uint32_t size;
            VG_REQUIRE(remaining, 1);
            type = *input++;
            remaining -= 1;
            if (type != instance->input_types[value_index]) {
                free(out);
                return VG_NATIVE_BAD_PAYLOAD;
            }
            size = type <= 3 ? 1 : (type <= 5 ? 2 : (type <= 8 ? 4 : 8));
            VG_REQUIRE(remaining, size);
            memcpy(instance->inputs + instance->input_offsets[value_index], input, size);
            input += size;
            remaining -= size;
        }
        instance->abi.Time = sample_time;
        VG_APPEND_U32(out, out_cursor, context->maximum_frame, id_size);
        VG_APPEND(out, out_cursor, context->maximum_frame, identifier, id_size);
        VG_APPEND_U32(out, out_cursor, context->maximum_frame, 1);
        {
            VgNativeStatus call_status = call_instance_function(
                context, instance, context->model_outputs,
                VG_NATIVE_OUTPUTS, out, &out_cursor, context->maximum_frame
            );
            if (call_status != VG_NATIVE_OK) {
                free(out);
                return call_status;
            }
        }
        VG_APPEND_U32(out, out_cursor, context->maximum_frame, instance->output_count);
        for (value_index = 0; value_index < instance->output_count; ++value_index) {
            uint8_t type = instance->output_types[value_index];
            uint32_t size = type <= 3 ? 1 : (type <= 5 ? 2 : (type <= 8 ? 4 : 8));
            VG_APPEND(out, out_cursor, context->maximum_frame, &type, 1);
            VG_APPEND(out, out_cursor, context->maximum_frame,
                      instance->outputs + instance->output_offsets[value_index], size);
        }
    }
    if (remaining != 0) {
        free(out);
        return VG_NATIVE_BAD_PAYLOAD;
    }
    *response = out;
    *response_size = out_cursor;
    return VG_NATIVE_OK;
}

VgNativeStatus handle_close(VgNativeWorkerContext *context, const uint8_t *payload,
                         uint64_t payload_size, uint8_t **response, uint64_t *response_size) {
    uint8_t *out;
    uint64_t cursor = 0;
    uint32_t termination_count = 0;
    uint32_t index;
    (void)payload;
    if (payload_size != 0) return VG_NATIVE_BAD_PAYLOAD;
    out = (uint8_t *)malloc((size_t)context->maximum_frame);
    if (out == NULL) return VG_NATIVE_ABI_FAILURE;
    for (index = 0; index < context->instance_count; ++index) {
        if (context->instances[index]->started && !context->instances[index]->terminated) {
            termination_count += 1;
        }
    }
    VG_APPEND_U32(out, cursor, context->maximum_frame, termination_count);
    for (index = 0; index < context->instance_count; ++index) {
        VgNativeInstance *instance = context->instances[index];
        if (instance->started && !instance->terminated) {
            uint32_t id_size = (uint32_t)strlen(instance->identifier);
            VG_APPEND_U32(out, cursor, context->maximum_frame, id_size);
            VG_APPEND(out, cursor, context->maximum_frame, instance->identifier, id_size);
            VgNativeStatus call_status = call_instance_function(
                context, instance, context->model_terminate,
                VG_NATIVE_TERMINATE, out, &cursor, context->maximum_frame
            );
            if (call_status != VG_NATIVE_OK) {
                free(out);
                return call_status;
            }
            instance->terminated = 1;
        }
    }
    context->state = VG_NATIVE_CLOSING;
    *response = out;
    *response_size = cursor;
    return VG_NATIVE_OK;
}

VgNativeStatus dispatch_request(VgNativeWorkerContext *context, const VgNativeFrameHeader *header,
                             const uint8_t *payload, uint8_t **response,
                             uint64_t *response_size) {
    if (context == NULL || header == NULL || response == NULL || response_size == NULL) {
        return VG_NATIVE_BAD_PAYLOAD;
    }
    *response = NULL;
    *response_size = 0;
    if (header->opcode == VG_NATIVE_INSPECT) {
        return handle_inspect(context, payload, header->payload_length, response, response_size);
    } else if (header->opcode == VG_NATIVE_PREPARE) {
        return handle_prepare(context, payload, header->payload_length, response, response_size);
    } else if (header->opcode == VG_NATIVE_INITIALIZE) {
        if (context->interface_kind > 1) {
            int status;
            if (context->state != VG_NATIVE_PREPARED && context->state != VG_NATIVE_ACTIVE) {
                return VG_NATIVE_BAD_STATE;
            }
            if (!vg_platform_module_guard_validate(
            &context->module_guard, &context->staged_file, context->system_path
    )) return VG_NATIVE_DEPENDENCY_FAILURE;
            status = context->interface_kind == 2
                ? vg_ieee_cigre_v1_0_initialize(&context->ieee_cigre_v1_0, payload, header->payload_length, response, response_size)
                : vg_iec_ese_initialize(&context->iec_ese, payload, header->payload_length, response, response_size);
            if (status == VG_NATIVE_OK) context->state = VG_NATIVE_ACTIVE;
            return (VgNativeStatus)status;
        }
        return handle_initialize(context, payload, header->payload_length, response, response_size);
    } else if (header->opcode == VG_NATIVE_SAMPLE) {
        if (context->interface_kind > 1) {
            if (context->state != VG_NATIVE_ACTIVE) return VG_NATIVE_BAD_STATE;
            if (!vg_platform_module_guard_validate(
            &context->module_guard, &context->staged_file, context->system_path
    )) return VG_NATIVE_DEPENDENCY_FAILURE;
            return (VgNativeStatus)(context->interface_kind == 2
                ? vg_ieee_cigre_v1_0_sample(&context->ieee_cigre_v1_0, payload, header->payload_length, response, response_size)
                : vg_iec_ese_sample(&context->iec_ese, payload, header->payload_length, response, response_size));
        }
        return handle_sample(context, payload, header->payload_length, response, response_size);
    } else if (header->opcode == VG_NATIVE_CLOSE) {
        if (context->interface_kind > 1) {
            int status = context->interface_kind == 2
                ? vg_ieee_cigre_v1_0_close(&context->ieee_cigre_v1_0, payload, header->payload_length, response, response_size)
                : vg_iec_ese_close(&context->iec_ese, payload, header->payload_length, response, response_size);
            if (status == VG_NATIVE_OK) context->state = VG_NATIVE_CLOSING;
            return (VgNativeStatus)status;
        }
        return handle_close(context, payload, header->payload_length, response, response_size);
    }
    return VG_NATIVE_BAD_OPCODE;
}

void close_worker_context(VgNativeWorkerContext *context) {
    uint32_t index;
    if (context == NULL) return;
    if (context->interface_kind == 1) {
        for (index = 0; index < context->instance_count; ++index) {
            VgNativeInstance *instance = context->instances[index];
            if (instance != NULL && instance->started && !instance->terminated
                    && context->model_terminate != NULL) {
                context->model_terminate(&instance->abi);
                instance->terminated = 1;
            }
            destroy_instance(instance);
        }
        free(context->instances);
    } else {
        if (context->interface_kind == 2) vg_ieee_cigre_v1_0_destroy(&context->ieee_cigre_v1_0);
        else vg_iec_ese_destroy(&context->iec_ese);
    }
    free(context->raw_model_info);
    vg_platform_module_guard_close(&context->module_guard);
    vg_platform_library_close(&context->vendor);
    vg_platform_file_close(&context->staged_file);
    vg_platform_capture_close(&context->capture);
    vg_platform_channel_close(&context->request_read);
    vg_platform_channel_close(&context->response_write);
}

int main(int argument_count, char **arguments) {
    VgNativeWorkerContext context;
    int running = 1;
    memset(&context, 0, sizeof(context));
    context.state = VG_NATIVE_CREATED;
    context.maximum_frame = 64ULL * 1024ULL * 1024ULL;
    vg_platform_file_initialize(&context.staged_file);
    vg_platform_library_initialize(&context.vendor);
    vg_platform_capture_initialize(&context.capture);
    vg_platform_module_guard_initialize(&context.module_guard);
    vg_ieee_cigre_v1_0_initialize_adapter(&context.ieee_cigre_v1_0);
    vg_iec_ese_initialize_adapter(&context.iec_ese);
    if (argument_count != 3) return 2;
    vg_platform_channel_initialize(&context.request_read, arguments[1]);
    vg_platform_channel_initialize(&context.response_write, arguments[2]);
    if (!vg_platform_channel_is_valid(&context.request_read)
            || !vg_platform_channel_is_valid(&context.response_write)) {
        return 3;
    }
    while (running) {
        uint8_t *body = NULL;
        uint64_t body_size = 0;
        int read_result = read_frame(&context, &body, &body_size);
        VgNativeFrameHeader header;
        const uint8_t *payload = NULL;
        VgNativeStatus status;
        uint8_t *response = NULL;
        uint64_t response_size = 0;
        const char *diagnostic = "";
        uint8_t *error_payload = NULL;
        uint64_t error_size = 0;
        if (read_result <= 0) {
            free(body);
            break;
        }
        memset(&header, 0, sizeof(header));
        status = decode_header(&context, body, body_size, &header, &payload);
        if (status == VG_NATIVE_OK) {
            status = dispatch_request(&context, &header, payload, &response, &response_size);
        }
        if (status == VG_NATIVE_BAD_MAGIC) diagnostic = "bad magic";
        else if (status == VG_NATIVE_BAD_VERSION) diagnostic = "bad version";
        else if (status == VG_NATIVE_BAD_KIND) diagnostic = "bad kind";
        else if (status == VG_NATIVE_BAD_OPCODE) diagnostic = "bad opcode";
        else if (status == VG_NATIVE_BAD_REQUEST_ID) diagnostic = "bad request id";
        else if (status == VG_NATIVE_BAD_LENGTH) diagnostic = "bad length";
        else if (status == VG_NATIVE_BAD_PAYLOAD) diagnostic = "bad payload";
        else if (status == VG_NATIVE_BAD_STATE) diagnostic = "bad state";
        else if (status == VG_NATIVE_ABI_FAILURE) diagnostic = "abi failure";
        else if (status == VG_NATIVE_DEPENDENCY_FAILURE) diagnostic = "dependency observation limit";
        else if (status == VG_NATIVE_CONTENT_IDENTITY_FAILURE) diagnostic = "content identity failure";
        if (status != VG_NATIVE_OK) {
            uint32_t diagnostic_size = (uint32_t)strlen(diagnostic);
            error_size = 4 + diagnostic_size;
            error_payload = (uint8_t *)malloc((size_t)error_size);
            if (error_payload == NULL) {
                free(response);
                free(body);
                break;
            }
            memcpy(error_payload, &diagnostic_size, 4);
            memcpy(error_payload + 4, diagnostic, diagnostic_size);
            free(response);
            response = error_payload;
            response_size = error_size;
        }
        if (!write_response(&context, header.opcode, header.request_id,
                            status, response, response_size)) {
            free(response);
            free(body);
            break;
        }
        if (status != VG_NATIVE_BAD_REQUEST_ID) {
            context.last_request_id = header.request_id;
            context.has_request_id = 1;
        }
        if ((status >= VG_NATIVE_BAD_MAGIC && status <= VG_NATIVE_BAD_PAYLOAD)
                || status >= VG_NATIVE_ABI_FAILURE || context.state == VG_NATIVE_CLOSING) {
            running = 0;
        }
        free(response);
        free(body);
    }
    close_worker_context(&context);
    return 0;
}
