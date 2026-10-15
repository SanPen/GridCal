/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 * SPDX-License-Identifier: MPL-2.0
 */
#ifndef VERAGRID_MANUFACTURER_PLATFORM_H
#define VERAGRID_MANUFACTURER_PLATFORM_H

#include <stdint.h>

#ifdef _WIN32
#define VG_PLATFORM_CDECL __cdecl
#else
#define VG_PLATFORM_CDECL
#endif

typedef struct VgPlatformChannel {
    intptr_t handle;
} VgPlatformChannel;

typedef struct VgPlatformFileIdentity {
    uint64_t device_identifier;
    uint8_t file_identifier[16];
} VgPlatformFileIdentity;

typedef struct VgPlatformFile {
    intptr_t handle;
    VgPlatformFileIdentity identity;
} VgPlatformFile;

typedef struct VgPlatformLibrary {
    uintptr_t handle;
    VgPlatformFileIdentity identity;
} VgPlatformLibrary;

typedef struct VgPlatformCapture {
    intptr_t original_output;
    intptr_t original_error;
    intptr_t output_file;
    intptr_t error_file;
} VgPlatformCapture;

typedef struct VgPlatformModuleGuard {
    VgPlatformFileIdentity *baseline;
    uint32_t baseline_count;
    uint32_t baseline_capacity;
    VgPlatformFileIdentity staged_library;
    VgPlatformFileIdentity system_directory;
    uint64_t observation_count;
    uint64_t maximum_observations;
} VgPlatformModuleGuard;

typedef struct VgPlatformSha256 {
    uint32_t state[8];
    uint64_t total_bytes;
    uint8_t block[64];
    uint32_t block_size;
} VgPlatformSha256;

void vg_platform_sha256_initialize(VgPlatformSha256 *context);
int vg_platform_sha256_update(VgPlatformSha256 *context, const uint8_t *bytes, uint64_t size);
int vg_platform_sha256_finalize(VgPlatformSha256 *context, uint8_t digest[32]);

void vg_platform_channel_initialize(VgPlatformChannel *channel, const char *argument);
int vg_platform_channel_is_valid(const VgPlatformChannel *channel);
int vg_platform_channel_read_some(VgPlatformChannel *channel, uint8_t *target,
                                  uint32_t capacity, uint32_t *received);
int vg_platform_channel_read_exact(VgPlatformChannel *channel, uint8_t *target, uint64_t size);
int vg_platform_channel_write_exact(VgPlatformChannel *channel, const uint8_t *source,
                                    uint64_t size);
void vg_platform_channel_close(VgPlatformChannel *channel);

void vg_platform_file_initialize(VgPlatformFile *file);
int vg_platform_file_is_valid(const VgPlatformFile *file);
int vg_platform_verify_file(const char *path, uint64_t expected_size,
                            const uint8_t *expected_sha256, uint8_t actual_sha256[32],
                            VgPlatformFile *retained_file);
void vg_platform_file_close(VgPlatformFile *file);
int vg_platform_executable_hash(uint8_t sha256[32]);

void vg_platform_library_initialize(VgPlatformLibrary *library);
int vg_platform_library_open(const char *path, const VgPlatformFile *verified_file,
                             VgPlatformLibrary *library);
void *vg_platform_library_symbol(const VgPlatformLibrary *library, const char *symbol_name);
void vg_platform_library_close(VgPlatformLibrary *library);

void vg_platform_capture_initialize(VgPlatformCapture *capture);
int vg_platform_capture_open(VgPlatformCapture *capture);
int vg_platform_capture_finish(VgPlatformCapture *capture, uint64_t maximum_size,
                               uint8_t **output_bytes, uint64_t *output_size,
                               uint8_t **error_bytes, uint64_t *error_size,
                               uint8_t *output_truncated, uint8_t *error_truncated);
void vg_platform_capture_close(VgPlatformCapture *capture);

void vg_platform_module_guard_initialize(VgPlatformModuleGuard *guard);
int vg_platform_module_guard_begin(VgPlatformModuleGuard *guard,
                                   uint64_t maximum_observations,
                                   const char *system_directory,
                                   const VgPlatformFileIdentity *expected_system_identity);
int vg_platform_module_guard_validate(VgPlatformModuleGuard *guard,
                                      const VgPlatformFile *staged_library,
                                      const char *system_directory);
void vg_platform_module_guard_close(VgPlatformModuleGuard *guard);
const char *vg_platform_runtime_library_name(void);

#endif