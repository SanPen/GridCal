/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 * SPDX-License-Identifier: MPL-2.0
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <link.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "platform.h"

static void vg_linux_file_identity(const struct stat *status,
                                   VgPlatformFileIdentity *identity) {
    uint64_t inode;
    memset(identity, 0, sizeof(*identity));
    identity->device_identifier = (uint64_t)status->st_dev;
    inode = (uint64_t)status->st_ino;
    memcpy(identity->file_identifier, &inode, sizeof(inode));
}

static int vg_platform_identity_equal(const VgPlatformFileIdentity *left,
                                      const VgPlatformFileIdentity *right) {
    if (left == NULL || right == NULL) {
        return 0;
    } else {
        return left->device_identifier == right->device_identifier
            && memcmp(left->file_identifier, right->file_identifier, 16) == 0;
    }
}

void vg_platform_channel_initialize(VgPlatformChannel *channel, const char *argument) {
    long parsed;
    char *end;
    if (channel != NULL) {
        channel->handle = -1;
        if (argument != NULL) {
            errno = 0;
            end = NULL;
            parsed = strtol(argument, &end, 10);
            if (errno == 0 && end != argument && end != NULL && *end == '\0'
                    && parsed >= 0 && parsed <= INT32_MAX) {
                channel->handle = (intptr_t)parsed;
            } else {
                channel->handle = -1;
            }
        } else {
            channel->handle = -1;
        }
    } else {
        return;
    }
}

int vg_platform_channel_is_valid(const VgPlatformChannel *channel) {
    if (channel == NULL) {
        return 0;
    } else {
        return channel->handle >= 0 && channel->handle <= INT32_MAX;
    }
}

int vg_platform_channel_read_some(VgPlatformChannel *channel, uint8_t *target,
                                  uint32_t capacity, uint32_t *received) {
    ssize_t result;
    if (!vg_platform_channel_is_valid(channel) || target == NULL || capacity == 0
            || received == NULL) {
        return 0;
    } else {
        do {
            result = read((int)channel->handle, target, capacity);
        } while (result < 0 && errno == EINTR);
        if (result < 0) {
            *received = 0;
            return 0;
        } else {
            *received = (uint32_t)result;
            return 1;
        }
    }
}

int vg_platform_channel_read_exact(VgPlatformChannel *channel, uint8_t *target, uint64_t size) {
    uint64_t completed;
    if (!vg_platform_channel_is_valid(channel) || (target == NULL && size != 0)) {
        return 0;
    } else {
        completed = 0;
        while (completed < size) {
            uint32_t capacity = (uint32_t)((size - completed) > 1048576ULL
                ? 1048576ULL : (size - completed));
            uint32_t received = 0;
            if (!vg_platform_channel_read_some(channel, target + completed, capacity, &received)
                    || received == 0) {
                return 0;
            } else {
                completed += received;
            }
        }
        return 1;
    }
}

int vg_platform_channel_write_exact(VgPlatformChannel *channel, const uint8_t *source,
                                    uint64_t size) {
    uint64_t completed;
    if (!vg_platform_channel_is_valid(channel) || (source == NULL && size != 0)) {
        return 0;
    } else {
        completed = 0;
        while (completed < size) {
            size_t chunk = (size_t)((size - completed) > 1048576ULL
                ? 1048576ULL : (size - completed));
            ssize_t written;
            do {
                written = write((int)channel->handle, source + completed, chunk);
            } while (written < 0 && errno == EINTR);
            if (written <= 0) {
                return 0;
            } else {
                completed += (uint64_t)written;
            }
        }
        return 1;
    }
}

void vg_platform_channel_close(VgPlatformChannel *channel) {
    if (vg_platform_channel_is_valid(channel)) {
        close((int)channel->handle);
        channel->handle = -1;
    } else if (channel != NULL) {
        channel->handle = -1;
    } else {
        return;
    }
}

void vg_platform_file_initialize(VgPlatformFile *file) {
    if (file != NULL) {
        memset(file, 0, sizeof(*file));
        file->handle = -1;
    } else {
        return;
    }
}

int vg_platform_file_is_valid(const VgPlatformFile *file) {
    if (file == NULL) {
        return 0;
    } else {
        return file->handle >= 0 && file->handle <= INT32_MAX;
    }
}

int vg_platform_verify_file(const char *path, uint64_t expected_size,
                            const uint8_t *expected_sha256, uint8_t actual_sha256[32],
                            VgPlatformFile *retained_file) {
    int descriptor;
    struct stat status;
    VgPlatformSha256 hash_context;
    uint8_t *buffer;
    int valid;
    if (path == NULL || actual_sha256 == NULL) {
        return 0;
    } else {
        descriptor = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    }
    if (descriptor < 0 || fstat(descriptor, &status) != 0 || !S_ISREG(status.st_mode)
            || status.st_size < 0
            || (expected_size != 0 && (uint64_t)status.st_size != expected_size)) {
        if (descriptor >= 0) {
            close(descriptor);
        } else {
            return 0;
        }
        return 0;
    } else {
        buffer = (uint8_t *)malloc(1048576U);
    }
    if (buffer == NULL) {
        close(descriptor);
        return 0;
    } else {
        vg_platform_sha256_initialize(&hash_context);
        valid = 1;
    }
    while (valid) {
        ssize_t received;
        do {
            received = read(descriptor, buffer, 1048576U);
        } while (received < 0 && errno == EINTR);
        if (received < 0) {
            valid = 0;
        } else if (received == 0) {
            break;
        } else {
            valid = vg_platform_sha256_update(&hash_context, buffer, (uint64_t)received);
        }
    }
    free(buffer);
    if (valid) {
        valid = vg_platform_sha256_finalize(&hash_context, actual_sha256);
    } else {
        valid = 0;
    }
    if (valid && expected_sha256 != NULL) {
        valid = memcmp(expected_sha256, actual_sha256, 32) == 0;
    } else {
        /* No caller-provided digest needs comparison. */
    }
    if (valid && retained_file != NULL) {
        if (lseek(descriptor, 0, SEEK_SET) < 0) {
            valid = 0;
            close(descriptor);
        } else {
            vg_platform_file_initialize(retained_file);
            retained_file->handle = descriptor;
            vg_linux_file_identity(&status, &retained_file->identity);
        }
    } else {
        close(descriptor);
    }
    return valid;
}

void vg_platform_file_close(VgPlatformFile *file) {
    if (vg_platform_file_is_valid(file)) {
        close((int)file->handle);
        vg_platform_file_initialize(file);
    } else if (file != NULL) {
        vg_platform_file_initialize(file);
    } else {
        return;
    }
}

int vg_platform_executable_hash(uint8_t sha256[32]) {
    char path[4096];
    ssize_t size;
    if (sha256 == NULL) {
        return 0;
    } else {
        size = readlink("/proc/self/exe", path, sizeof(path) - 1U);
    }
    if (size <= 0 || (size_t)size >= sizeof(path)) {
        return 0;
    } else {
        path[size] = '\0';
        return vg_platform_verify_file(path, 0, NULL, sha256, NULL);
    }
}
void vg_platform_library_initialize(VgPlatformLibrary *library) {
    if (library != NULL) {
        memset(library, 0, sizeof(*library));
    } else {
        return;
    }
}

int vg_platform_library_open(const char *path, const VgPlatformFile *verified_file,
                             VgPlatformLibrary *library) {
    void *handle;
    struct link_map *mapping;
    int descriptor;
    struct stat status;
    VgPlatformFileIdentity loaded_identity;
    int valid;
    if (path == NULL || !vg_platform_file_is_valid(verified_file) || library == NULL) {
        return 0;
    } else {
        vg_platform_library_initialize(library);
        handle = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    }
    mapping = NULL;
    valid = handle != NULL && dlinfo(handle, RTLD_DI_LINKMAP, &mapping) == 0
        && mapping != NULL && mapping->l_name != NULL && mapping->l_name[0] != '\0';
    if (valid) {
        descriptor = open(mapping->l_name, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    } else {
        descriptor = -1;
    }
    if (descriptor >= 0 && fstat(descriptor, &status) == 0 && S_ISREG(status.st_mode)) {
        vg_linux_file_identity(&status, &loaded_identity);
        valid = vg_platform_identity_equal(&verified_file->identity, &loaded_identity);
    } else {
        valid = 0;
    }
    if (descriptor >= 0) {
        close(descriptor);
    } else {
        valid = 0;
    }
    if (valid) {
        library->handle = (uintptr_t)handle;
        library->identity = loaded_identity;
    } else if (handle != NULL) {
        dlclose(handle);
    } else {
        return 0;
    }
    return valid;
}

void *vg_platform_library_symbol(const VgPlatformLibrary *library, const char *symbol_name) {
    if (library == NULL || library->handle == 0 || symbol_name == NULL) {
        return NULL;
    } else {
        return dlsym((void *)library->handle, symbol_name);
    }
}

void vg_platform_library_close(VgPlatformLibrary *library) {
    if (library != NULL && library->handle != 0) {
        dlclose((void *)library->handle);
        vg_platform_library_initialize(library);
    } else if (library != NULL) {
        vg_platform_library_initialize(library);
    } else {
        return;
    }
}
void vg_platform_capture_initialize(VgPlatformCapture *capture) {
    if (capture != NULL) {
        capture->original_output = -1;
        capture->original_error = -1;
        capture->output_file = -1;
        capture->error_file = -1;
    } else {
        return;
    }
}

int vg_platform_capture_open(VgPlatformCapture *capture) {
    char output_template[] = "/tmp/veragrid-oem-output-XXXXXX";
    char error_template[] = "/tmp/veragrid-oem-error-XXXXXX";
    int output_file;
    int error_file;
    if (capture == NULL) {
        return 0;
    } else {
        vg_platform_capture_initialize(capture);
        output_file = mkstemp(output_template);
        error_file = mkstemp(error_template);
    }
    if (output_file >= 0) {
        unlink(output_template);
    } else {
        output_file = -1;
    }
    if (error_file >= 0) {
        unlink(error_template);
    } else {
        error_file = -1;
    }
    if (output_file < 0 || error_file < 0) {
        if (output_file >= 0) {
            close(output_file);
        } else {
            output_file = -1;
        }
        if (error_file >= 0) {
            close(error_file);
        } else {
            error_file = -1;
        }
        return 0;
    } else {
        capture->original_output = dup(STDOUT_FILENO);
        capture->original_error = dup(STDERR_FILENO);
        capture->output_file = output_file;
        capture->error_file = error_file;
    }
    if (capture->original_output < 0 || capture->original_error < 0
            || dup2(output_file, STDOUT_FILENO) < 0 || dup2(error_file, STDERR_FILENO) < 0) {
        vg_platform_capture_close(capture);
        return 0;
    } else {
        return 1;
    }
}

int vg_platform_capture_finish(VgPlatformCapture *capture, uint64_t maximum_size,
                               uint8_t **output_bytes, uint64_t *output_size,
                               uint8_t **error_bytes, uint64_t *error_size,
                               uint8_t *output_truncated, uint8_t *error_truncated) {
    int files[2];
    uint8_t **targets[2];
    uint64_t *sizes[2];
    uint8_t *truncations[2];
    uint32_t index;
    if (capture == NULL || capture->output_file < 0 || capture->error_file < 0
            || output_bytes == NULL || output_size == NULL || error_bytes == NULL
            || error_size == NULL || output_truncated == NULL || error_truncated == NULL) {
        return 0;
    } else {
        fflush(NULL);
    }
    if (fsync((int)capture->output_file) != 0 || fsync((int)capture->error_file) != 0
            || dup2((int)capture->original_output, STDOUT_FILENO) < 0
            || dup2((int)capture->original_error, STDERR_FILENO) < 0) {
        return 0;
    } else {
        files[0] = (int)capture->output_file;
        files[1] = (int)capture->error_file;
        targets[0] = output_bytes;
        targets[1] = error_bytes;
        sizes[0] = output_size;
        sizes[1] = error_size;
        truncations[0] = output_truncated;
        truncations[1] = error_truncated;
    }
    for (index = 0; index < 2U; ++index) {
        struct stat status;
        uint64_t retained_size;
        if (fstat(files[index], &status) != 0 || status.st_size < 0
                || lseek(files[index], 0, SEEK_SET) < 0) {
            return 0;
        } else {
            retained_size = (uint64_t)status.st_size;
        }
        if (retained_size > maximum_size) {
            retained_size = maximum_size;
            *truncations[index] = 1;
        } else {
            *truncations[index] = 0;
        }
        *targets[index] = (uint8_t *)malloc((size_t)(retained_size == 0 ? 1 : retained_size));
        if (*targets[index] == NULL) {
            return 0;
        } else {
            *sizes[index] = 0;
        }
        while (*sizes[index] < retained_size) {
            size_t capacity = (size_t)((retained_size - *sizes[index]) > 1048576ULL
                ? 1048576ULL : (retained_size - *sizes[index]));
            ssize_t received;
            do {
                received = read(files[index], *targets[index] + *sizes[index], capacity);
            } while (received < 0 && errno == EINTR);
            if (received <= 0) {
                return 0;
            } else {
                *sizes[index] += (uint64_t)received;
            }
        }
    }
    return 1;
}

void vg_platform_capture_close(VgPlatformCapture *capture) {
    if (capture != NULL) {
        if (capture->output_file >= 0) {
            close((int)capture->output_file);
        } else {
            capture->output_file = -1;
        }
        if (capture->error_file >= 0) {
            close((int)capture->error_file);
        } else {
            capture->error_file = -1;
        }
        if (capture->original_output >= 0) {
            close((int)capture->original_output);
        } else {
            capture->original_output = -1;
        }
        if (capture->original_error >= 0) {
            close((int)capture->original_error);
        } else {
            capture->original_error = -1;
        }
        vg_platform_capture_initialize(capture);
    } else {
        return;
    }
}
static int vg_linux_module_is_baseline(const VgPlatformModuleGuard *guard,
                                       const VgPlatformFileIdentity *identity) {
    uint32_t index;
    int found;
    if (guard == NULL || identity == NULL) {
        return 0;
    } else {
        index = 0;
        found = 0;
    }
    while (index < guard->baseline_count && !found) {
        found = vg_platform_identity_equal(&guard->baseline[index], identity);
        index += 1;
    }
    return found;
}

static int vg_linux_read_module_identity(const char *path,
                                         VgPlatformFileIdentity *identity) {
    struct stat status;
    if (path == NULL || identity == NULL || stat(path, &status) != 0
            || !S_ISREG(status.st_mode)) {
        return 0;
    } else {
        vg_linux_file_identity(&status, identity);
        return 1;
    }
}

static int vg_linux_collect_modules(VgPlatformModuleGuard *guard,
                                    const VgPlatformFile *staged_library,
                                    int store_baseline) {
    FILE *mapping_file;
    char line[8192];
    int valid;
    if (guard == NULL || (store_baseline != 0 && store_baseline != 1)) {
        return 0;
    } else {
        mapping_file = fopen("/proc/self/maps", "r");
    }
    if (mapping_file == NULL) {
        return 0;
    } else {
        valid = 1;
    }
    while (valid && fgets(line, sizeof(line), mapping_file) != NULL) {
        char *path = strchr(line, '/');
        if (path != NULL) {
            size_t path_size = strlen(path);
            VgPlatformFileIdentity identity;
            while (path_size > 0
                    && (path[path_size - 1U] == '\n' || path[path_size - 1U] == '\r')) {
                path_size -= 1U;
                path[path_size] = '\0';
            }
            if (!vg_linux_read_module_identity(path, &identity)) {
                valid = 0;
            } else if (store_baseline) {
                if (!vg_linux_module_is_baseline(guard, &identity)) {
                    if (guard->baseline_count >= guard->baseline_capacity) {
                        valid = 0;
                    } else {
                        guard->baseline[guard->baseline_count] = identity;
                        guard->baseline_count += 1;
                    }
                } else {
                    /* Repeated memory mappings retain one file identity. */
                }
            } else if (!vg_linux_module_is_baseline(guard, &identity)
                    && (staged_library == NULL
                        || !vg_platform_identity_equal(&staged_library->identity, &identity))) {
                valid = 0;
            } else {
                /* The mapping belongs to the baseline or verified OEM library. */
            }
        } else {
            /* Anonymous and kernel mappings have no external file dependency. */
        }
    }
    if (ferror(mapping_file) != 0) {
        valid = 0;
    } else {
        /* End of file completed the module observation. */
    }
    fclose(mapping_file);
    return valid;
}

void vg_platform_module_guard_initialize(VgPlatformModuleGuard *guard) {
    if (guard != NULL) {
        memset(guard, 0, sizeof(*guard));
    } else {
        return;
    }
}

int vg_platform_module_guard_begin(VgPlatformModuleGuard *guard,
                                   uint64_t maximum_observations,
                                   const char *system_directory,
                                   const VgPlatformFileIdentity *expected_system_identity) {
    VgPlatformFileIdentity empty_identity;
    if (guard == NULL || maximum_observations == 0 || system_directory == NULL
            || expected_system_identity == NULL) {
        return 0;
    } else {
        memset(&empty_identity, 0, sizeof(empty_identity));
    }
    if (system_directory[0] != '\0'
            || !vg_platform_identity_equal(expected_system_identity, &empty_identity)) {
        return 0;
    } else {
        vg_platform_module_guard_initialize(guard);
        guard->maximum_observations = maximum_observations;
        guard->baseline_capacity = 4096U;
        guard->baseline = (VgPlatformFileIdentity *)calloc(
            guard->baseline_capacity, sizeof(VgPlatformFileIdentity)
        );
    }
    if (guard->baseline == NULL) {
        return 0;
    } else {
        guard->observation_count = 1;
    }
    if (guard->observation_count > guard->maximum_observations
            || !vg_linux_collect_modules(guard, NULL, 1)) {
        vg_platform_module_guard_close(guard);
        return 0;
    } else {
        return 1;
    }
}

int vg_platform_module_guard_validate(VgPlatformModuleGuard *guard,
                                      const VgPlatformFile *staged_library,
                                      const char *system_directory) {
    if (guard == NULL || guard->baseline == NULL
            || !vg_platform_file_is_valid(staged_library)
            || system_directory == NULL || system_directory[0] != '\0'
            || guard->observation_count == UINT64_MAX) {
        return 0;
    } else {
        guard->observation_count += 1;
    }
    if (guard->observation_count > guard->maximum_observations) {
        return 0;
    } else {
        return vg_linux_collect_modules(guard, staged_library, 0);
    }
}

void vg_platform_module_guard_close(VgPlatformModuleGuard *guard) {
    if (guard != NULL) {
        free(guard->baseline);
        vg_platform_module_guard_initialize(guard);
    } else {
        return;
    }
}

const char *vg_platform_runtime_library_name(void) {
    return "libc.so.6";
}