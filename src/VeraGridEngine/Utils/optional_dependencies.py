"""Diagnostics for failures confined to optional third-party imports."""

from importlib.metadata import PackageNotFoundError, version
import warnings


def optional_dependency_failure(package_name: str, error: Exception) -> str:
    """Describe an unavailable integration and warn only for broken installations.

    :param package_name: Distribution name of the optional dependency.
    :param error: Failure raised while importing or checking its required API.
    :return: Reason suitable for a feature's logger or availability status.
    """
    # Upgrading VeraGrid does not upgrade optional packages: stale APIs and native ABI
    # mismatches must disable the integration instead of preventing application startup.
    # Call this only at third-party import/API boundaries; do not hide model or solver errors.
    module_name: str = package_name.replace('-', '_')
    # Missing optional packages are normal; missing transitive dependencies indicate a broken install.
    if isinstance(error, ModuleNotFoundError) and error.name == module_name:
        return f"{package_name} is not installed; install it in this Python environment and restart VeraGrid"
    else:
        # Distribution metadata is readable even when the native module cannot load.
        try:
            installed_version: str = version(package_name)
        except PackageNotFoundError:
            installed_version = 'unknown version'
        reason: str = (
            f"{package_name} {installed_version} could not initialize: {error}. "
            "Install a compatible version in this Python environment and restart VeraGrid"
        )
        warnings.warn(f"Optional integration disabled: {reason}", stacklevel=2)
        return reason
