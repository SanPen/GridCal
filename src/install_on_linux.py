#!/usr/bin/env python3
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
install_on_linux.py

Installs VeraGrid on a Linux desktop system by:
- Creating a dedicated virtual environment in $HOME (under ~/.local/share/veragrid/venv).
- Installing the veragrid package into the virtual environment.
- Installing the application icon into ~/.local/share/veragrid/ and standard icon directories.
- Creating the desktop entry at $HOME/.local/share/applications/veragrid.desktop.
- Associating .veragrid and .gridcal files with VeraGrid via shared-mime-info and xdg-mime.
- Registering the desktop entry using update-desktop-database.
"""

import os
import sys
import stat
import shutil
import argparse
import subprocess
from pathlib import Path


class LinuxInstallConfig:
    """
    Configuration holder for Linux installation parameters.
    """

    __slots__ = (
        "_venv_dir",
        "_desktop_file",
        "_python_interpreter",
        "_package_target",
        "_system_site_packages",
        "_terminal",
        "_skip_pip",
        "_associate_mime",
    )

    def __init__(
        self,
        venv_dir: Path,
        desktop_file: Path,
        python_interpreter: Path,
        package_target: str,
        system_site_packages: bool,
        terminal: bool,
        skip_pip: bool,
        associate_mime: bool,
    ) -> None:
        """
        Initialize the installation configuration.

        :param venv_dir: Directory where the virtual environment will reside.
        :type venv_dir: Path
        :param desktop_file: Destination path of the desktop file.
        :type desktop_file: Path
        :param python_interpreter: Base Python interpreter used to create the venv.
        :type python_interpreter: Path
        :param package_target: Package name or path to install via pip.
        :type package_target: str
        :param system_site_packages: Whether to enable system site packages in the venv.
        :type system_site_packages: bool
        :param terminal: Whether the desktop entry should run inside a terminal.
        :type terminal: bool
        :param skip_pip: Whether to skip running pip install.
        :type skip_pip: bool
        :param associate_mime: Whether to associate .veragrid and .gridcal files with VeraGrid.
        :type associate_mime: bool
        """
        self._venv_dir: Path = venv_dir
        self._desktop_file: Path = desktop_file
        self._python_interpreter: Path = python_interpreter
        self._package_target: str = package_target
        self._system_site_packages: bool = system_site_packages
        self._terminal: bool = terminal
        self._skip_pip: bool = skip_pip
        self._associate_mime: bool = associate_mime

    def get_venv_dir(self) -> Path:
        """
        Get the target virtual environment directory.

        :return: Path to the venv directory.
        :rtype: Path
        """
        return self._venv_dir

    def get_desktop_file(self) -> Path:
        """
        Get the target desktop file path.

        :return: Path to the desktop file.
        :rtype: Path
        """
        return self._desktop_file

    def get_python_interpreter(self) -> Path:
        """
        Get the base Python interpreter path.

        :return: Path to the base Python executable.
        :rtype: Path
        """
        return self._python_interpreter

    def get_package_target(self) -> str:
        """
        Get the target pip package to install.

        :return: Name or path of the package target.
        :rtype: str
        """
        return self._package_target

    def get_system_site_packages(self) -> bool:
        """
        Get whether system site packages are enabled.

        :return: Flag indicating system-site-packages inclusion.
        :rtype: bool
        """
        return self._system_site_packages

    def get_terminal(self) -> bool:
        """
        Get whether to launch the app in a terminal.

        :return: Flag indicating terminal execution.
        :rtype: bool
        """
        return self._terminal

    def get_skip_pip(self) -> bool:
        """
        Get whether pip installation step should be skipped.

        :return: Flag indicating if pip should be skipped.
        :rtype: bool
        """
        return self._skip_pip

    def get_associate_mime(self) -> bool:
        """
        Get whether .veragrid and .gridcal file associations should be performed.

        :return: Flag indicating MIME type association.
        :rtype: bool
        """
        return self._associate_mime


def is_linux_platform() -> bool:
    """
    Check if the current operating system is Linux.

    :return: True if the platform is Linux, False otherwise.
    :rtype: bool
    """
    # Verify the operating system platform begins with linux
    is_linux: bool = sys.platform.startswith("linux")
    if is_linux:
        return True
    else:
        return False


def test_python_venv_capability(candidate_executable: Path) -> bool:
    """
    Test whether a Python candidate executable can invoke venv and ensurepip.

    :param candidate_executable: Candidate Python binary to test.
    :type candidate_executable: Path
    :return: True if the candidate can create venvs with pip, False otherwise.
    :rtype: bool
    """
    # Check if the executable file exists and is executable on the file system
    exists: bool = candidate_executable.is_file()
    if exists:
        # Run a short check to verify that both venv and ensurepip modules can be imported
        cmd: list[str] = list()
        cmd.append(str(candidate_executable))
        cmd.append("-c")
        cmd.append("import venv, ensurepip")

        proc_result: subprocess.CompletedProcess[bytes] = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if proc_result.returncode == 0:
            return True
        else:
            return False
    else:
        return False


def find_system_python() -> Path | None:
    """
    Locate a system Python 3 interpreter capable of virtual environment creation.

    :return: Path to the discovered Python executable, or None if not found.
    :rtype: Path | None
    """
    # Build the sequence of candidate Python interpreters in priority order
    candidates: list[Path] = list()

    # Check standard system binary paths first
    candidates.append(Path("/usr/bin/python3"))
    candidates.append(Path("/usr/local/bin/python3"))

    # Check the base python of the current runtime if running inside a virtualenv
    base_prefix_python: Path = Path(sys.base_prefix) / "bin" / "python3"
    candidates.append(base_prefix_python)

    # Check PATH lookup
    which_python: str | None = shutil.which("python3")
    if which_python is not None:
        candidates.append(Path(which_python))
    else:
        pass

    # Check currently running executable
    candidates.append(Path(sys.executable))

    # Iterate through candidates and select the first working one
    selected_python: Path | None = None
    for candidate in candidates:
        if selected_python is None:
            can_create_venv: bool = test_python_venv_capability(candidate)
            if can_create_venv:
                selected_python = candidate
            else:
                pass
        else:
            pass

    return selected_python


def create_virtual_environment(config: LinuxInstallConfig) -> Path | None:
    """
    Create or update a virtual environment using the configured Python interpreter.

    :param config: Linux installation configuration instance.
    :type config: LinuxInstallConfig
    :return: Path to the virtual environment python executable, or None if failed.
    :rtype: Path | None
    """
    venv_dir: Path = config.get_venv_dir()
    python_interpreter: Path = config.get_python_interpreter()
    system_site_packages: bool = config.get_system_site_packages()

    # Create parent folder if not present
    parent_dir: Path = venv_dir.parent
    if not parent_dir.exists():
        parent_dir.mkdir(parents=True, exist_ok=True)
    else:
        pass

    # Assemble the venv creation command line
    cmd: list[str] = list()
    cmd.append(str(python_interpreter))
    cmd.append("-m")
    cmd.append("venv")

    # If requested by configuration, enable system site packages inside the venv
    if system_site_packages:
        cmd.append("--system-site-packages")
    else:
        pass

    cmd.append(str(venv_dir))

    print(f"Creating virtual environment at: {venv_dir}")
    print(f"Using base Python interpreter: {python_interpreter}")

    # Execute the command to create the virtual environment
    proc_result: subprocess.CompletedProcess[bytes] = subprocess.run(cmd)
    if proc_result.returncode != 0:
        print(f"Error: Failed to create virtual environment (exit code {proc_result.returncode})")
        return None
    else:
        venv_python: Path = venv_dir / "bin" / "python3"
        if venv_python.exists():
            return venv_python
        else:
            print(f"Error: Virtual environment python executable not found at: {venv_python}")
            return None


def install_package_into_venv(venv_python: Path, package_target: str) -> bool:
    """
    Install the specified package target into the virtual environment using pip.

    :param venv_python: Path to the virtual environment's python executable.
    :type venv_python: Path
    :param package_target: Package name, wheel, or directory target for pip install.
    :type package_target: str
    :return: True if installation succeeded, False otherwise.
    :rtype: bool
    """
    # First, attempt to upgrade pip inside the virtual environment
    upgrade_cmd: list[str] = list()
    upgrade_cmd.append(str(venv_python))
    upgrade_cmd.append("-m")
    upgrade_cmd.append("pip")
    upgrade_cmd.append("install")
    upgrade_cmd.append("--upgrade")
    upgrade_cmd.append("pip")

    print("Upgrading pip in the virtual environment...")
    upgrade_result: subprocess.CompletedProcess[bytes] = subprocess.run(upgrade_cmd)
    if upgrade_result.returncode != 0:
        print("Notice: pip upgrade did not complete successfully; continuing with package installation.")
    else:
        print("pip is up to date.")

    # Next, install the target package
    install_cmd: list[str] = list()
    install_cmd.append(str(venv_python))
    install_cmd.append("-m")
    install_cmd.append("pip")
    install_cmd.append("install")
    install_cmd.append("--no-user")
    install_cmd.append("--disable-pip-version-check")
    install_cmd.append(package_target)

    print(f"Installing '{package_target}' into the virtual environment...")
    install_result: subprocess.CompletedProcess[bytes] = subprocess.run(install_cmd)
    if install_result.returncode == 0:
        print(f"Successfully installed '{package_target}' into the virtual environment.")
        return True
    else:
        print(f"Error: pip install failed with exit code {install_result.returncode}.")
        return False


def resolve_and_copy_icon(target_dir: Path) -> Path | None:
    """
    Find the VeraGrid icon and copy it to the user application asset directory.

    :param target_dir: Application directory where the icon will be preserved.
    :type target_dir: Path
    :return: Path to the destination icon file, or None if no icon could be resolved.
    :rtype: Path | None
    """
    # Ensure the destination directory exists
    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)
    else:
        pass

    # Destination icon path
    dest_icon: Path = target_dir / "veragrid.png"

    # Build candidate paths to find existing icon files
    candidate_icons: list[Path] = list()

    # 1. Script relative repository paths
    script_dir: Path = Path(__file__).resolve().parent
    candidate_icons.append(script_dir.parent / "pics" / "VeraGrid_icon.png")
    candidate_icons.append(script_dir / "VeraGrid" / "Gui" / "Icons" / "icons" / "VeraGrid_icon.png")

    # 2. Cache directory path
    candidate_icons.append(Path.home() / ".cache" / "veragrid" / "veragrid.png")

    # 3. Check if target icon already exists
    candidate_icons.append(dest_icon)

    # Find the first candidate that exists
    found_source: Path | None = None
    for candidate in candidate_icons:
        if found_source is None:
            if candidate.is_file():
                found_source = candidate
            else:
                pass
        else:
            pass

    if found_source is not None:
        # If the found source is different from the destination, copy it
        if found_source != dest_icon:
            shutil.copy2(found_source, dest_icon)
        else:
            pass

        # Also copy to standard XDG hicolor icon theme if directory exists
        hicolor_dir: Path = Path.home() / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps"
        if not hicolor_dir.exists():
            hicolor_dir.mkdir(parents=True, exist_ok=True)
        else:
            pass
        hicolor_icon: Path = hicolor_dir / "veragrid.png"
        shutil.copy2(dest_icon, hicolor_icon)

        return dest_icon
    else:
        print("Warning: Could not locate VeraGrid icon file.")
        return None


def generate_mime_xml_content() -> str:
    """
    Generate the shared MIME info XML definition for .veragrid and .gridcal formats.

    :return: XML content defining application/x-veragrid and application/x-gridcal MIME types.
    :rtype: str
    """
    lines: list[str] = list()
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">')
    lines.append('    <mime-type type="application/x-veragrid">')
    lines.append('        <comment>VeraGrid Project</comment>')
    lines.append('        <glob pattern="*.veragrid" weight="65"/>')
    lines.append('        <icon name="application-x-veragrid"/>')
    lines.append('    </mime-type>')
    lines.append('    <mime-type type="application/x-gridcal">')
    lines.append('        <comment>GridCal Project</comment>')
    lines.append('        <glob pattern="*.gridcal" weight="65"/>')
    lines.append('        <glob pattern="*.dgridcal" weight="65"/>')
    lines.append('        <icon name="application-x-gridcal"/>')
    lines.append('    </mime-type>')
    lines.append('</mime-info>')
    lines.append('')

    return "\n".join(lines)


def register_veragrid_mime_type(icon_file: Path | None) -> bool:
    """
    Register application/x-veragrid and application/x-gridcal MIME types and associate with VeraGrid.

    :param icon_file: Path to the VeraGrid application icon file.
    :type icon_file: Path | None
    :return: True if MIME registration completed without fatal errors, False otherwise.
    :rtype: bool
    """
    home_dir: Path = Path.home()
    mime_packages_dir: Path = home_dir / ".local" / "share" / "mime" / "packages"
    if not mime_packages_dir.exists():
        mime_packages_dir.mkdir(parents=True, exist_ok=True)
    else:
        pass

    # Write the shared-mime-info package definition
    mime_file: Path = mime_packages_dir / "veragrid.xml"
    xml_content: str = generate_mime_xml_content()
    mime_file.write_text(xml_content, encoding="utf-8")
    print(f"Created MIME type definition at: {mime_file}")

    # Copy mime icon to standard hicolor mimetypes directory if icon is provided
    if icon_file is not None:
        mimetypes_icon_dir: Path = home_dir / ".local" / "share" / "icons" / "hicolor" / "256x256" / "mimetypes"
        if not mimetypes_icon_dir.exists():
            mimetypes_icon_dir.mkdir(parents=True, exist_ok=True)
        else:
            pass
        mime_icon_veragrid: Path = mimetypes_icon_dir / "application-x-veragrid.png"
        shutil.copy2(icon_file, mime_icon_veragrid)
        mime_icon_gridcal: Path = mimetypes_icon_dir / "application-x-gridcal.png"
        shutil.copy2(icon_file, mime_icon_gridcal)
    else:
        pass

    # Update the user MIME database
    mime_base_dir: Path = home_dir / ".local" / "share" / "mime"
    updater: str | None = shutil.which("update-mime-database")
    if updater is not None:
        update_cmd: list[str] = list()
        update_cmd.append(updater)
        update_cmd.append(str(mime_base_dir))
        proc_result: subprocess.CompletedProcess[bytes] = subprocess.run(
            update_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if proc_result.returncode == 0:
            print("Updated user MIME database successfully.")
        else:
            print(f"Notice: update-mime-database exited with code {proc_result.returncode}.")
    else:
        pass

    # Set veragrid.desktop as the default handler for application/x-veragrid and application/x-gridcal
    xdg_mime_bin: str | None = shutil.which("xdg-mime")
    if xdg_mime_bin is not None:
        mime_types: list[str] = list()
        mime_types.append("application/x-veragrid")
        mime_types.append("application/x-gridcal")
        for mime_tpe in mime_types:
            default_cmd: list[str] = list()
            default_cmd.append(xdg_mime_bin)
            default_cmd.append("default")
            default_cmd.append("veragrid.desktop")
            default_cmd.append(mime_tpe)
            default_result: subprocess.CompletedProcess[bytes] = subprocess.run(
                default_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if default_result.returncode == 0:
                print(f"Associated {mime_tpe} files with veragrid.desktop via xdg-mime.")
            else:
                print(f"Notice: xdg-mime default command exited with code {default_result.returncode} for {mime_tpe}.")
    else:
        pass

    return True


def build_desktop_entry_text(exec_command: str, icon_file: Path | None, terminal_flag: bool) -> str:
    """
    Generate the formatted text of a standard FreeDesktop .desktop entry.

    :param exec_command: Command line string for the Exec entry.
    :type exec_command: str
    :param icon_file: Absolute path to the icon file, or None if unavailable.
    :type icon_file: Path | None
    :param terminal_flag: Flag whether Terminal execution is requested.
    :type terminal_flag: bool
    :return: Content of the desktop entry file.
    :rtype: str
    """
    terminal_str: str = "true" if terminal_flag else "false"
    icon_str: str = str(icon_file) if icon_file is not None else "veragrid"

    lines: list[str] = list()
    lines.append("[Desktop Entry]")
    lines.append("Version=1.1")
    lines.append("Type=Application")
    lines.append("Name=VeraGrid")
    lines.append("GenericName=Power Systems Simulator")
    lines.append("Comment=Power Systems simulation program intended for professional use and research")
    lines.append(f"Icon={icon_str}")
    lines.append(f"Exec={exec_command} %F")
    lines.append(f"Terminal={terminal_str}")
    lines.append("Actions=")
    lines.append("MimeType=application/x-veragrid;application/x-gridcal;")
    lines.append("Categories=Science;Engineering;")
    lines.append("StartupNotify=true")
    lines.append("StartupWMClass=veragrid")
    lines.append("")

    return "\n".join(lines)


def create_desktop_entry(config: LinuxInstallConfig, icon_file: Path | None) -> bool:
    """
    Write the desktop entry file and register it in the desktop environment.

    :param config: Linux installation configuration instance.
    :type config: LinuxInstallConfig
    :param icon_file: Absolute path to the icon file, or None if unavailable.
    :type icon_file: Path | None
    :return: True if creation and validation succeeded, False otherwise.
    :rtype: bool
    """
    desktop_file: Path = config.get_desktop_file()
    venv_dir: Path = config.get_venv_dir()
    terminal: bool = config.get_terminal()

    # Ensure destination parent directory exists
    parent_dir: Path = desktop_file.parent
    if not parent_dir.exists():
        parent_dir.mkdir(parents=True, exist_ok=True)
    else:
        pass

    # Determine the executable command
    veragrid_bin: Path = venv_dir / "bin" / "veragrid"
    exec_cmd: str = ""
    if veragrid_bin.is_file():
        exec_cmd = str(veragrid_bin)
    else:
        venv_python: Path = venv_dir / "bin" / "python3"
        exec_cmd = f'{venv_python} -c "from VeraGrid.ExecuteVeraGrid import runVeraGrid; runVeraGrid()"'

    desktop_content: str = build_desktop_entry_text(
        exec_command=exec_cmd,
        icon_file=icon_file,
        terminal_flag=terminal,
    )

    # Write the desktop file
    desktop_file.write_text(desktop_content, encoding="utf-8")

    # Set permissions to executable: rwxr-xr-x
    current_mode: int = desktop_file.stat().st_mode
    desktop_file.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Created desktop entry at: {desktop_file}")

    # Validate desktop file if desktop-file-validate is available
    validator: str | None = shutil.which("desktop-file-validate")
    if validator is not None:
        val_cmd: list[str] = list()
        val_cmd.append(validator)
        val_cmd.append(str(desktop_file))
        val_result: subprocess.CompletedProcess[bytes] = subprocess.run(
            val_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if val_result.returncode != 0:
            err_msg: str = val_result.stderr.decode("utf-8", errors="replace")
            print(f"Warning: Desktop file validation produced warnings: {err_msg}")
        else:
            print("Desktop entry validation passed successfully.")
    else:
        pass

    # Update desktop database if update-desktop-database is available
    updater: str | None = shutil.which("update-desktop-database")
    if updater is not None:
        update_cmd: list[str] = list()
        update_cmd.append(updater)
        update_cmd.append(str(parent_dir))
        subprocess.run(
            update_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("Updated desktop application database.")
    else:
        pass

    return True


def build_config_from_args(raw_args: list[str]) -> LinuxInstallConfig | None:
    """
    Parse command line arguments and build the installation configuration.

    :param raw_args: Raw arguments list (typically sys.argv[1:]).
    :type raw_args: list[str]
    :return: LinuxInstallConfig instance if valid, or None if configuration failed.
    :rtype: LinuxInstallConfig | None
    """
    home_dir: Path = Path.home()
    default_venv: Path = home_dir / ".local" / "share" / "veragrid" / "venv"
    default_desktop: Path = home_dir / ".local" / "share" / "applications" / "veragrid.desktop"

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Install VeraGrid on Linux: create virtual environment, desktop entry, and file associations."
    )

    parser.add_argument(
        "--venv-dir",
        type=str,
        default=str(default_venv),
        help=f"Virtual environment directory (default: {default_venv})",
    )
    parser.add_argument(
        "--desktop-file",
        type=str,
        default=str(default_desktop),
        help=f"Desktop entry destination (default: {default_desktop})",
    )
    parser.add_argument(
        "--python",
        type=str,
        default=None,
        help="Base Python interpreter used to create the virtual environment.",
    )
    parser.add_argument(
        "--package",
        type=str,
        default="veragrid",
        help="Pip package specification to install (default: 'veragrid').",
    )
    parser.add_argument(
        "--no-system-site-packages",
        action="store_true",
        default=False,
        help="Do not include system site packages in the virtual environment.",
    )
    parser.add_argument(
        "--no-terminal",
        action="store_true",
        default=False,
        help="Set Terminal=false in the desktop entry.",
    )
    parser.add_argument(
        "--skip-pip",
        action="store_true",
        default=False,
        help="Skip running pip install into the virtual environment.",
    )
    parser.add_argument(
        "--no-mime",
        action="store_true",
        default=False,
        help="Skip registering .veragrid MIME type association.",
    )

    parsed_args: argparse.Namespace = parser.parse_args(raw_args)

    # Resolve the python interpreter
    chosen_python: Path | None = None
    if parsed_args.python is not None:
        custom_python: Path = Path(parsed_args.python)
        if custom_python.is_file():
            chosen_python = custom_python
        else:
            print(f"Error: Specified Python interpreter does not exist: {custom_python}")
            return None
    else:
        chosen_python = find_system_python()

    if chosen_python is None:
        print("Error: Could not locate a working system Python interpreter to create the virtual environment.")
        return None
    else:
        pass

    use_system_site_packages: bool = not parsed_args.no_system_site_packages
    use_terminal: bool = not parsed_args.no_terminal
    associate_mime: bool = not parsed_args.no_mime

    config: LinuxInstallConfig = LinuxInstallConfig(
        venv_dir=Path(parsed_args.venv_dir),
        desktop_file=Path(parsed_args.desktop_file),
        python_interpreter=chosen_python,
        package_target=parsed_args.package,
        system_site_packages=use_system_site_packages,
        terminal=use_terminal,
        skip_pip=parsed_args.skip_pip,
        associate_mime=associate_mime,
    )

    return config


def run_installation(config: LinuxInstallConfig) -> int:
    """
    Run the end-to-end Linux installation workflow.

    :param config: Linux installation configuration instance.
    :type config: LinuxInstallConfig
    :return: 0 on success, non-zero exit code on failure.
    :rtype: int
    """
    print("=" * 60)
    print("Starting VeraGrid Linux Installation")
    print("=" * 60)

    # Step 1: Verify platform
    is_linux: bool = is_linux_platform()
    if not is_linux:
        print("Error: This installer is intended for Linux platforms only.")
        return 1
    else:
        pass

    # Step 2: Create virtual environment
    venv_python: Path | None = create_virtual_environment(config=config)
    if venv_python is None:
        print("Error: Virtual environment creation failed.")
        return 2
    else:
        print(f"Virtual environment created successfully at: {config.get_venv_dir()}")

    # Step 3: Install VeraGrid package via pip unless skipped
    skip_pip: bool = config.get_skip_pip()
    if not skip_pip:
        install_success: bool = install_package_into_venv(
            venv_python=venv_python,
            package_target=config.get_package_target(),
        )
        if not install_success:
            print("Warning: Package installation via pip reported an error.")
        else:
            pass
    else:
        print("Skipping pip package installation as requested.")

    # Step 4: Resolve and install icon
    icon_file: Path | None = resolve_and_copy_icon(target_dir=config.get_venv_dir().parent)

    # Step 5: Create and configure desktop entry
    desktop_created: bool = create_desktop_entry(
        config=config,
        icon_file=icon_file,
    )
    if not desktop_created:
        print("Error: Failed to create desktop entry.")
        return 3
    else:
        pass

    # Step 6: Register .veragrid and .gridcal file associations if enabled
    associate_mime: bool = config.get_associate_mime()
    if associate_mime:
        mime_registered: bool = register_veragrid_mime_type(icon_file=icon_file)
        if not mime_registered:
            print("Notice: File association MIME type registration did not complete.")
        else:
            print("Registered .veragrid and .gridcal file associations successfully.")
    else:
        print("Skipping MIME type registration as requested.")

    print("=" * 60)
    print("VeraGrid Linux Installation Completed Successfully!")
    print(f"Virtual environment: {config.get_venv_dir()}")
    print(f"Desktop entry:       {config.get_desktop_file()}")
    if icon_file is not None:
        print(f"Application icon:    {icon_file}")
    else:
        pass
    print("File associations:   .veragrid, .gridcal -> VeraGrid")
    print("=" * 60)

    return 0


def main() -> int:
    """
    Main entry point for Linux installer script.

    :return: Process exit code.
    :rtype: int
    """
    raw_args: list[str] = list(sys.argv[1:])
    config: LinuxInstallConfig | None = build_config_from_args(raw_args=raw_args)
    if config is None:
        return 1
    else:
        return run_installation(config=config)


if __name__ == "__main__":
    exit_code: int = main()
    sys.exit(exit_code)
