# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import copy
import hashlib
from typing import Tuple

from VeraGridEngine.Devices.Parents.editable_device import EditableDevice, GCProp
from VeraGridEngine.enumerations import (
    DeviceType,
    IeeeCigreDllPlatform,
    IeeeCigreDllVerificationStatus,
    NativeModelInterface,
    SubObjectType,
)


class ManufacturerNativeBinaryVariant:
    """Persistent identity and verification state of one platform binary."""

    __slots__ = (
        "platform", "extension", "content_sha256", "byte_size", "zip_member", "verification_status",
    )

    def __init__(self,
                 platform: IeeeCigreDllPlatform,
                 extension: str,
                 content_sha256: str,
                 byte_size: int,
                 zip_member: str,
                 verification_status: IeeeCigreDllVerificationStatus) -> None:
        """Create a complete platform variant record.

        :param platform: Exact operating-system and architecture pair.
        :param extension: Native filename suffix including its leading dot.
        :param content_sha256: Lowercase SHA-256 of the exact manufacturer bytes.
        :param byte_size: Exact binary size in bytes.
        :param zip_member: Content-addressed member owned by the VeraGrid archive.
        :param verification_status: Import and instance-isolation qualification status.
        :return: None.
        """
        expected_extension: str
        if platform in (IeeeCigreDllPlatform.WINDOWS_X86, IeeeCigreDllPlatform.WINDOWS_X64):
            expected_extension = ".dll"
        else:
            if platform == IeeeCigreDllPlatform.LINUX_X64:
                expected_extension = ".so"
            else:
                raise ValueError("Unsupported manufacturer native platform")
        if extension != expected_extension:
            raise ValueError(f"Platform {platform.value} requires {expected_extension}")
        else:
            pass
        normalized_sha256: str = content_sha256.lower()
        if len(normalized_sha256) != 64 or any(char not in "0123456789abcdef" for char in normalized_sha256):
            raise ValueError("Manufacturer native binary SHA-256 is invalid")
        else:
            pass
        if byte_size < 1 or byte_size > 512 * 1024 * 1024:
            raise ValueError("Manufacturer native binary size is outside 1..512 MiB")
        else:
            pass
        expected_member: str = (
            "native_models/manufacturer/by_sha256/"
            + normalized_sha256
            + expected_extension
        )
        platform_member: str = (
            "native_models/manufacturer/"
            + platform.value
            + "/"
            + normalized_sha256
            + expected_extension
        )
        legacy_member: str = (
            "native_models/manufacturer/ieee_cigre_v1_1/"
            + platform.value
            + "/"
            + normalized_sha256
            + expected_extension
        )
        if zip_member not in (expected_member, platform_member, legacy_member):
            raise ValueError("Manufacturer native ZIP member is not canonical")
        else:
            pass
        self.platform: IeeeCigreDllPlatform = platform
        self.extension: str = extension
        self.content_sha256: str = normalized_sha256
        self.byte_size: int = byte_size
        self.zip_member: str = zip_member
        self.verification_status: IeeeCigreDllVerificationStatus = verification_status


class ManufacturerNativeBinarySource:
    """Nonpersistent locator from which FileSave can stream one verified variant."""

    __slots__ = ("platform", "file_path", "archive_path", "archive_member")

    def __init__(self,
                 platform: IeeeCigreDllPlatform,
                 file_path: str = "",
                 archive_path: str = "",
                 archive_member: str = "") -> None:
        """Create a source locator for a file or one archive member.

        :param platform: Platform variant provided by this source.
        :param file_path: Imported manufacturer file, when source bytes are external.
        :param archive_path: VeraGrid archive containing the source bytes.
        :param archive_member: Member inside ``archive_path``.
        :return: None.
        """
        has_file: bool = len(file_path) > 0
        has_archive: bool = len(archive_path) > 0 or len(archive_member) > 0
        if has_file == has_archive:
            raise ValueError("Binary source must select exactly one file or archive member")
        else:
            pass
        if has_archive and (len(archive_path) == 0 or len(archive_member) == 0):
            raise ValueError("Archive binary source requires both archive path and member")
        else:
            pass
        self.platform: IeeeCigreDllPlatform = platform
        self.file_path: str = file_path
        self.archive_path: str = archive_path
        self.archive_member: str = archive_member


class ManufacturerNativeModel(EditableDevice):
    """Canonical provider for one manufacturer model and its platform binaries."""

    __slots__ = (
        "_native_interface",
        "_model_info_schema_version",
        "_model_info",
        "_model_info_sha256",
        "_windows_x86_variant",
        "_windows_x64_variant",
        "_linux_x64_variant",
        "_windows_x86_source",
        "_windows_x64_source",
        "_linux_x64_source",
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(
            prop_name="native_interface",
            units="",
            tpe=NativeModelInterface,
            definition="Native manufacturer interface contract",
            editable=False,
            display=True,
        ),
        GCProp(
            prop_name="model_info_schema_version",
            units="",
            tpe=int,
            definition="VeraGrid canonical ModelInfo schema version",
            editable=False,
            display=False,
        ),
        GCProp(
            prop_name="model_info",
            units="",
            tpe=SubObjectType.ManufacturerNativeModelInfo,
            definition="Exact canonical IEEE/CIGRE ModelInfo bytes",
            editable=False,
            display=False,
        ),
        GCProp(
            prop_name="model_info_sha256",
            units="",
            tpe=str,
            definition="SHA-256 of the exact canonical ModelInfo bytes",
            editable=False,
            display=True,
        ),
    )

    def __init__(self, idtag: str = "", name: str = "") -> None:
        """Create an empty manufacturer native provider.

        :param idtag: Stable provider identifier.
        :param name: Display name.
        :return: None.
        """
        super().__init__(
            name=name,
            idtag=idtag,
            code="",
            device_type=DeviceType.ManufacturerNativeModelDevice,
            comment="",
        )
        self._native_interface: NativeModelInterface = NativeModelInterface.IEEE_CIGRE_V1_1
        self._model_info_schema_version: int = 1
        self._model_info: bytes = bytes()
        self._model_info_sha256: str = ""
        self._windows_x86_variant: ManufacturerNativeBinaryVariant | None = None
        self._windows_x64_variant: ManufacturerNativeBinaryVariant | None = None
        self._linux_x64_variant: ManufacturerNativeBinaryVariant | None = None
        self._windows_x86_source: ManufacturerNativeBinarySource | None = None
        self._windows_x64_source: ManufacturerNativeBinarySource | None = None
        self._linux_x64_source: ManufacturerNativeBinarySource | None = None

    def __deepcopy__(self, memo: dict[int, object]) -> "ManufacturerNativeModel":
        """Copy provider data while retaining immutable content identities.

        :param memo: Standard deepcopy memo table.
        :return: Independent provider copy without consumer changes.
        """
        result: ManufacturerNativeModel = ManufacturerNativeModel(idtag=self.idtag, name=self.name)
        memo[id(self)] = result
        result.code = self.code
        result.rdfid = self.rdfid
        result.comment = self.comment
        result.action = self.action
        result.selected_to_merge = self.selected_to_merge
        result.diff_changes = copy.deepcopy(self.diff_changes, memo)
        result._native_interface = self._native_interface
        result._model_info_schema_version = self._model_info_schema_version
        result._model_info = self._model_info
        result._model_info_sha256 = self._model_info_sha256
        result._windows_x86_variant = copy.deepcopy(self._windows_x86_variant, memo)
        result._windows_x64_variant = copy.deepcopy(self._windows_x64_variant, memo)
        result._linux_x64_variant = copy.deepcopy(self._linux_x64_variant, memo)
        result._windows_x86_source = copy.deepcopy(self._windows_x86_source, memo)
        result._windows_x64_source = copy.deepcopy(self._windows_x64_source, memo)
        result._linux_x64_source = copy.deepcopy(self._linux_x64_source, memo)
        return result

    def copy(self, forced_new_idtag: bool = False) -> "ManufacturerNativeModel":
        """Copy the complete provider through the ordinary asset contract.

        :param forced_new_idtag: Generate an independent provider identity when true.
        :return: Complete provider copy with independent variant and source records.
        """
        result: ManufacturerNativeModel = copy.deepcopy(self)
        if forced_new_idtag:
            result.generate_uuid()
        else:
            pass
        return result

    @property
    def native_interface(self) -> NativeModelInterface:
        """Return the ABI identity.

        :return: Native model interface.
        """
        return self._native_interface

    @native_interface.setter
    def native_interface(self, value: NativeModelInterface) -> None:
        """Set the ABI identity.

        :param value: Native model interface.
        :return: None.
        """
        if value in (
                NativeModelInterface.IEEE_CIGRE_V1_1,
                NativeModelInterface.IEEE_CIGRE_V1_0,
                NativeModelInterface.IEC_ESE,
        ):
            self._native_interface = value
        else:
            raise ValueError("Unsupported manufacturer native interface")

    @property
    def model_info_schema_version(self) -> int:
        """Return the canonical metadata schema version.

        :return: Metadata schema version.
        """
        return self._model_info_schema_version

    @model_info_schema_version.setter
    def model_info_schema_version(self, value: int) -> None:
        """Set the canonical metadata schema version.

        :param value: Required schema version.
        :return: None.
        """
        if value in (1, 2):
            self._model_info_schema_version = value
        else:
            raise ValueError("Unsupported canonical ModelInfo schema version")

    @property
    def model_info(self) -> bytes:
        """Return the exact canonical ModelInfo bytes.

        :return: Immutable canonical bytes.
        """
        return self._model_info

    @model_info.setter
    def model_info(self, value: bytes) -> None:
        """Store exact canonical bytes and derive their content digest.

        :param value: Canonical metadata bytes validated by the IO codec.
        :return: None.
        """
        if not isinstance(value, bytes) or len(value) == 0:
            raise ValueError("Canonical ModelInfo bytes cannot be empty")
        else:
            pass
        if value.startswith(b"veragrid-manufacturer-native-model-info-v2\n"):
            schema_version: int = 2
        else:
            if value.startswith(b"veragrid-ieee-cigre-model-info-v1\n"):
                schema_version = 1
            else:
                raise ValueError("Canonical ModelInfo schema prefix is unsupported")
        self._model_info_schema_version = schema_version
        self._model_info = value
        self._model_info_sha256 = hashlib.sha256(value).hexdigest()

    @property
    def model_info_sha256(self) -> str:
        """Return the canonical metadata SHA-256.

        :return: Lowercase hexadecimal digest.
        """
        return self._model_info_sha256

    @model_info_sha256.setter
    def model_info_sha256(self, value: str) -> None:
        """Verify a persisted metadata digest against the stored bytes.

        :param value: Persisted lowercase hexadecimal digest.
        :return: None.
        """
        if value.lower() != self._model_info_sha256:
            raise ValueError("Persisted ModelInfo SHA-256 does not match canonical bytes")
        else:
            self._model_info_sha256 = value.lower()

    def get_platform_variant(self,
                             platform: IeeeCigreDllPlatform) -> ManufacturerNativeBinaryVariant | None:
        """Return the binary variant for one exact host platform.

        :param platform: Exact host platform.
        :return: Platform variant or ``None`` when unavailable.
        """
        if platform == IeeeCigreDllPlatform.WINDOWS_X86:
            return self._windows_x86_variant
        else:
            if platform == IeeeCigreDllPlatform.WINDOWS_X64:
                return self._windows_x64_variant
            else:
                if platform == IeeeCigreDllPlatform.LINUX_X64:
                    return self._linux_x64_variant
                else:
                    raise ValueError("Unsupported manufacturer native platform")

    def set_platform_variant(self, variant: ManufacturerNativeBinaryVariant) -> None:
        """Store one complete verified platform variant.

        :param variant: Complete typed variant record.
        :return: None.
        """
        if variant.platform == IeeeCigreDllPlatform.WINDOWS_X86:
            self._windows_x86_variant = variant
        else:
            if variant.platform == IeeeCigreDllPlatform.WINDOWS_X64:
                self._windows_x64_variant = variant
            else:
                if variant.platform == IeeeCigreDllPlatform.LINUX_X64:
                    self._linux_x64_variant = variant
                else:
                    raise ValueError("Unsupported manufacturer native platform")

    def clear_platform_variant(self, platform: IeeeCigreDllPlatform) -> None:
        """Remove one platform variant and its operational source.

        :param platform: Exact platform to remove.
        :return: None.
        """
        if platform == IeeeCigreDllPlatform.WINDOWS_X86:
            self._windows_x86_variant = None
            self._windows_x86_source = None
        else:
            if platform == IeeeCigreDllPlatform.WINDOWS_X64:
                self._windows_x64_variant = None
                self._windows_x64_source = None
            else:
                if platform == IeeeCigreDllPlatform.LINUX_X64:
                    self._linux_x64_variant = None
                    self._linux_x64_source = None
                else:
                    raise ValueError("Unsupported manufacturer native platform")

    def set_binary_source(self, source: ManufacturerNativeBinarySource) -> None:
        """Assign the nonpersistent source for one stored platform variant.

        :param source: File or archive-member locator.
        :return: None.
        """
        if self.get_platform_variant(source.platform) is None:
            raise ValueError("Cannot assign a source without its platform variant")
        else:
            pass
        if source.platform == IeeeCigreDllPlatform.WINDOWS_X86:
            self._windows_x86_source = source
        else:
            if source.platform == IeeeCigreDllPlatform.WINDOWS_X64:
                self._windows_x64_source = source
            else:
                if source.platform == IeeeCigreDllPlatform.LINUX_X64:
                    self._linux_x64_source = source
                else:
                    raise ValueError("Unsupported manufacturer native platform")

    def get_binary_source(self,
                          platform: IeeeCigreDllPlatform) -> ManufacturerNativeBinarySource | None:
        """Return the nonpersistent byte source for one platform.

        :param platform: Exact platform variant.
        :return: Source locator or ``None`` when it has not been bound.
        """
        if platform == IeeeCigreDllPlatform.WINDOWS_X86:
            return self._windows_x86_source
        else:
            if platform == IeeeCigreDllPlatform.WINDOWS_X64:
                return self._windows_x64_source
            else:
                if platform == IeeeCigreDllPlatform.LINUX_X64:
                    return self._linux_x64_source
                else:
                    raise ValueError("Unsupported manufacturer native platform")
