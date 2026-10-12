/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 * SPDX-License-Identifier: MPL-2.0
 */
#ifndef VERAGRID_MANUFACTURER_NATIVE_PROTOCOL_H
#define VERAGRID_MANUFACTURER_NATIVE_PROTOCOL_H

#include <stdint.h>

typedef enum VgNativeOpcode {
    VG_NATIVE_INSPECT = 1,
    VG_NATIVE_PREPARE = 2,
    VG_NATIVE_INITIALIZE = 3,
    VG_NATIVE_SAMPLE = 4,
    VG_NATIVE_CLOSE = 5
} VgNativeOpcode;

typedef enum VgNativeMessageKind {
    VG_NATIVE_REQUEST = 1,
    VG_NATIVE_RESPONSE = 2
} VgNativeMessageKind;

typedef enum VgNativeStatus {
    VG_NATIVE_OK = 0,
    VG_NATIVE_BAD_MAGIC = 1,
    VG_NATIVE_BAD_VERSION = 2,
    VG_NATIVE_BAD_KIND = 3,
    VG_NATIVE_BAD_OPCODE = 4,
    VG_NATIVE_BAD_REQUEST_ID = 5,
    VG_NATIVE_BAD_LENGTH = 6,
    VG_NATIVE_BAD_PAYLOAD = 7,
    VG_NATIVE_BAD_STATE = 8,
    VG_NATIVE_ABI_FAILURE = 9,
    VG_NATIVE_DEPENDENCY_FAILURE = 10,
    VG_NATIVE_CONTENT_IDENTITY_FAILURE = 11
} VgNativeStatus;

typedef enum VgNativeCallOperation {
    VG_NATIVE_FIRST_CALL = 1,
    VG_NATIVE_CHECK_PARAMETERS = 2,
    VG_NATIVE_INITIALIZE_CALL = 3,
    VG_NATIVE_OUTPUTS = 4,
    VG_NATIVE_TERMINATE = 5
} VgNativeCallOperation;

typedef enum VgNativeWorkerState {
    VG_NATIVE_CREATED = 0,
    VG_NATIVE_INSPECTED = 1,
    VG_NATIVE_PREPARED = 2,
    VG_NATIVE_ACTIVE = 3,
    VG_NATIVE_CLOSING = 4
} VgNativeWorkerState;

#pragma pack(push, 1)
typedef struct VgNativeFrameHeader {
    uint8_t magic[4];
    uint16_t version;
    uint8_t kind;
    uint8_t opcode;
    uint32_t request_id;
    uint32_t status;
    uint64_t payload_length;
} VgNativeFrameHeader;
#pragma pack(pop)

int vg_native_bounded_text_size(const char *text, uint64_t maximum_size,
                                uint64_t *text_size);

#endif
