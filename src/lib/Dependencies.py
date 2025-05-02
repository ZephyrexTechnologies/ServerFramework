"""
Dependencies.py - Module to analyze and resolve dependencies between Python modules
and to manage system and Python package dependencies.
"""

import logging
import os
import platform
import subprocess
import sys
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Tuple, Type

import pkg_resources
from pydantic import BaseModel, Field

# Import for better OS detection
try:
    import distro

    HAS_DISTRO = True
except ImportError:
    HAS_DISTRO = False

# Import for dependency resolution
try:
    import resolvelib
    from resolvelib.providers import AbstractProvider
    from resolvelib.resolvers import RequirementInformation, Resolver

    HAS_RESOLVELIB = True
except ImportError:
    HAS_RESOLVELIB = False

    # Create stub classes to avoid errors when importing
    class AbstractProvider:
        pass

    class Resolver:
        def __init__(self, provider, reporter=None):
            pass


# Common utility function for executing shell commands
def execute_command(
    cmd: List[str], check: bool = False, capture_output: bool = True, text: bool = True
) -> Tuple[bool, str, str]:
    """
    Execute a shell command with standardized error handling.

    Args:
        cmd: Command as list of string arguments
        check: Whether to raise an exception on failure
        capture_output: Whether to capture stdout/stderr
        text: Whether to return stdout/stderr as text

    Returns:
        Tuple of (success, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd, capture_output=capture_output, text=text, check=check
        )
        return (
            result.returncode == 0,
            result.stdout if hasattr(result, "stdout") else "",
            result.stderr if hasattr(result, "stderr") else "",
        )
    except FileNotFoundError:
        return False, "", f"Command not found: {cmd[0]}"
    except subprocess.SubprocessError as e:
        return False, "", str(e)
    except Exception as e:
        return False, "", str(e)


class Dependency(BaseModel):
    """Base class for all types of dependencies."""

    name: str = Field(..., description="Name of the dependency.")
    friendly_name: str = Field(..., description="The friendly name of the dependency.")
    optional: bool = Field(False, description="Whether this dependency is optional.")
    reason: str = Field(
        "None specified.",
        description="The reason this dependency is required and what it adds if optional.",
    )
    semver: Optional[str] = Field(
        None, description="Semantic version requirement (e.g., '>=1.0.0')"
    )


class SystemPackageMapping(BaseModel):
    """Package mapping for a specific package manager."""

    manager: str
    package_name: str


class SYS_Dependency(Dependency):
    """
    Base class for system dependencies across different package managers.
    """

    package_mappings: List[SystemPackageMapping] = Field(
        default_factory=list,
        description="Package mappings for different package managers",
    )

    def is_satisfied(self) -> bool:
        """
        Check if the dependency is satisfied on the current OS.

        Returns:
            bool: True if the dependency is installed by any available package manager
        """
        available_managers = get_available_package_managers()

        if not available_managers:
            logging.warning(
                f"No supported package managers found for dependency {self.name}"
            )
            return self.optional

        # Check if any of our package mappings match available package managers
        for mapping in self.package_mappings:
            if mapping.manager in available_managers:
                manager_cls = available_managers[mapping.manager]
                if manager_cls.check_package_installed(mapping.package_name):
                    return True

        # No matching package found or none installed
        return self.optional


class PIP_Dependency(Dependency):
    """
    Represents a dependency on a Python package.
    """

    def is_satisfied(self) -> bool:
        """
        Check if this PIP dependency is satisfied.

        Returns:
            bool: True if the dependency is installed with correct version
        """
        try:
            # Check if package is installed
            pkg_resources.get_distribution(self.name)

            # If semver is specified, check version
            if self.semver:
                try:
                    import semver

                    installed_version = pkg_resources.get_distribution(
                        self.name
                    ).version
                    return semver.match(installed_version, self.semver)
                except (ValueError, ImportError):
                    logging.warning(
                        f"Cannot verify version for {self.name}: requirement '{self.semver}'"
                    )
                    return True

            return True
        except pkg_resources.DistributionNotFound:
            return self.optional
        except Exception as e:
            logging.error(f"Error checking PIP dependency {self.name}: {str(e)}")
            return self.optional


class BREW_Dependency(SYS_Dependency):
    """
    Represents a dependency on a Homebrew package (macOS).
    For backward compatibility.
    """

    brew_package: Optional[str] = Field(None, description="Homebrew package name")

    def __init__(self, **data):
        super().__init__(**data)
        # Ensure brew_package is set from name for backward compatibility
        if self.brew_package is None:
            self.brew_package = self.name


class WINGET_Dependency(SYS_Dependency):
    """
    Represents a dependency on a WinGet package (Windows).
    For backward compatibility.
    """

    winget_package: Optional[str] = Field(None, description="WinGet package name")

    def __init__(self, **data):
        super().__init__(**data)
        # Ensure winget_package is set from name for backward compatibility
        if self.winget_package is None:
            self.winget_package = self.name


def check_system_dependencies(dependencies: List[SYS_Dependency]) -> Dict[str, bool]:
    """
    Check if system dependencies are satisfied.

    Args:
        dependencies: List of SYS_Dependency objects

    Returns:
        Dict mapping dependency names to whether they are satisfied
    """
    result = {}
    for dep in dependencies:
        result[dep.name] = dep.is_satisfied()
        if not result[dep.name] and not dep.optional:
            logging.warning(f"Required system dependency '{dep.name}' is not installed")

    return result


# Helper function for version checking
def check_version_compatibility(
    installed_version: str, required_version: Optional[str]
) -> bool:
    """
    Check if an installed version is compatible with a requirement.

    Args:
        installed_version: Currently installed version
        required_version: Required version constraint (e.g., ">=1.0.0")

    Returns:
        bool: True if the version is compatible, False otherwise
    """
    if not required_version:
        return True

    try:
        import semver

        return semver.match(installed_version, required_version)
    except (ImportError, ValueError):
        logging.warning(
            f"Cannot verify version: {installed_version} against requirement '{required_version}'"
        )
        return True  # Assume compatible if we can't check


class OSType(str, Enum):
    """Enumeration of supported operating systems."""

    DEBIAN = "debian"
    UBUNTU = "ubuntu"
    FEDORA = "fedora"
    REDHAT = "redhat"
    MACOS = "macos"
    WINDOWS = "windows"
    UNKNOWN = "unknown"


def get_os_type() -> OSType:
    """
    Detect the operating system type.
    Uses the distro package if available for more robust detection.

    Returns:
        OSType: Detected operating system
    """
    system = platform.system().lower()

    if system == "linux":
        # Use distro package if available for more robust detection
        if HAS_DISTRO:
            distro_id = distro.id()
            distro_like = distro.like() or ""

            if distro_id == "ubuntu" or "ubuntu" in distro_like:
                return OSType.UBUNTU
            elif distro_id == "debian" or "debian" in distro_like:
                return OSType.DEBIAN
            elif distro_id == "fedora" or "fedora" in distro_like:
                return OSType.FEDORA
            elif distro_id == "rhel" or distro_id == "centos" or "rhel" in distro_like:
                return OSType.REDHAT
            else:
                return OSType.UNKNOWN

        # Fall back to file-based detection if distro is not available
        if os.path.exists("/etc/debian_version"):
            with open("/etc/debian_version", "r") as f:
                version = f.read().strip()
            if os.path.exists("/etc/lsb-release"):
                with open("/etc/lsb-release", "r") as f:
                    if "ubuntu" in f.read().lower():
                        return OSType.UBUNTU
            return OSType.DEBIAN
        elif os.path.exists("/etc/fedora-release"):
            return OSType.FEDORA
        elif os.path.exists("/etc/redhat-release"):
            return OSType.REDHAT
        else:
            # If no specific Linux distribution is identified, return UNKNOWN
            return OSType.UNKNOWN
    elif system == "darwin":
        return OSType.MACOS
    elif system == "windows":
        return OSType.WINDOWS
    else:
        return OSType.UNKNOWN


class PackageManager(ABC):
    """Abstract base class for package managers."""

    # Dictionary mapping commands to their respective arguments
    COMMANDS = {}

    # List of supported operating systems
    SUPPORTED_OS = []

    @classmethod
    def _build_command(cls, command_type: str, *args) -> List[str]:
        """
        Build a command using the COMMANDS template.

        Args:
            command_type: Type of command (check, install, etc.)
            *args: Arguments to include in the command

        Returns:
            List[str]: Complete command
        """
        if command_type not in cls.COMMANDS:
            raise ValueError(f"Unsupported command type: {command_type}")

        command_template = cls.COMMANDS[command_type]
        command = []

        # Process each part of the command template
        for part in command_template:
            if part == "%args%":
                # Replace with all arguments
                command.extend(args)
            elif part.startswith("%arg"):
                # Replace with a specific argument index
                try:
                    index = int(part[4:-1])  # Extract index from %argN%
                    if index < len(args):
                        command.append(args[index])
                except (ValueError, IndexError):
                    # Skip invalid argument references
                    pass
            else:
                # Add the template part as-is
                command.append(part)

        return command

    @classmethod
    def _execute(
        cls, command_type: str, *args, sudo: bool = False
    ) -> Tuple[bool, str, str]:
        """
        Build and execute a command.

        Args:
            command_type: Type of command (check, install, etc.)
            *args: Arguments to include in the command
            sudo: Whether to prepend sudo to the command

        Returns:
            Tuple[bool, str, str]: (success, stdout, stderr)
        """
        cmd = cls._build_command(command_type, *args)

        # Add sudo if requested and not already present
        if sudo and cmd and cmd[0] != "sudo":
            cmd = ["sudo"] + cmd

        return execute_command(cmd)

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Check if this package manager is available on the system."""
        pass

    @classmethod
    def check_package_installed(cls, package_name: str) -> bool:
        """
        Check if a package is installed.

        Args:
            package_name: Name of the package to check

        Returns:
            bool: True if the package is installed
        """
        success, stdout, _ = cls._execute("check", package_name)
        return success and cls._is_package_in_output(package_name, stdout)

    @classmethod
    def _is_package_in_output(cls, package_name: str, output: str) -> bool:
        """
        Check if a package is present in command output.
        Default implementation just checks if the name is in the output.
        Override for package managers with specific output formats.

        Args:
            package_name: Name of the package
            output: Command output to check

        Returns:
            bool: True if the package is found in the output
        """
        return package_name in output

    @classmethod
    def install_package(cls, package_name: str) -> bool:
        """
        Install a package.

        Args:
            package_name: Name of the package to install

        Returns:
            bool: True if installation was successful
        """
        success, _, stderr = cls._execute("install", package_name, sudo=True)
        if not success:
            logging.error(f"Failed to install {package_name}: {stderr}")
        return success

    @classmethod
    def batch_install_packages(cls, package_names: List[str]) -> Dict[str, bool]:
        """
        Install multiple packages.
        Default implementation attempts batch installation first,
        then falls back to individual installation if needed.

        Args:
            package_names: List of package names to install

        Returns:
            Dict[str, bool]: Mapping of package names to installation success
        """
        if not package_names:
            return {}

        results = {}

        # Try batch installation if supported
        if hasattr(cls, "SUPPORTS_BATCH") and cls.SUPPORTS_BATCH:
            success, _, _ = cls._execute("batch_install", *package_names, sudo=True)

            if success:
                # All packages installed successfully
                return {pkg: True for pkg in package_names}

        # Fall back to individual installation
        for pkg_name in package_names:
            results[pkg_name] = cls.install_package(pkg_name)

        return results

    @classmethod
    def supports_os(cls, os_type: OSType) -> bool:
        """
        Check if this package manager supports the given OS.

        Args:
            os_type: Operating system to check

        Returns:
            bool: True if the OS is supported
        """
        return os_type in cls.SUPPORTED_OS


class APTPackageManager(PackageManager):
    """Package manager for APT (Debian, Ubuntu)."""

    SUPPORTED_OS = [OSType.DEBIAN, OSType.UBUNTU]
    SUPPORTS_BATCH = True

    COMMANDS = {
        "version": ["apt-get", "--version"],
        "check": ["dpkg-query", "-W", "-f=${Status}", "%arg0%"],
        "install": ["apt-get", "install", "-y", "%arg0%"],
        "batch_install": ["apt-get", "install", "-y", "%args%"],
        "update": ["apt-get", "update", "-qq"],
    }

    @classmethod
    def is_available(cls) -> bool:
        success, _, _ = cls._execute("version")
        return success

    @classmethod
    def _is_package_in_output(cls, package_name: str, output: str) -> bool:
        return "install ok installed" in output

    @classmethod
    def batch_install_packages(cls, package_names: List[str]) -> Dict[str, bool]:
        if not package_names:
            return {}

        results = {}

        # Update package lists first
        cls._execute("update", sudo=True)

        # Try batch installation
        success, _, _ = cls._execute("batch_install", *package_names, sudo=True)

        if success:
            # All packages installed successfully
            return {pkg: True for pkg in package_names}
        else:
            # Fall back to individual installation
            for pkg_name in package_names:
                results[pkg_name] = cls.install_package(pkg_name)

        return results


class SnapPackageManager(PackageManager):
    """Package manager for Snap (Ubuntu, other Linux)."""

    SUPPORTED_OS = [OSType.UBUNTU, OSType.DEBIAN, OSType.FEDORA, OSType.REDHAT]

    COMMANDS = {
        "version": ["snap", "--version"],
        "check": ["snap", "list", "%arg0%"],
        "install": ["snap", "install", "%arg0%"],
    }

    @classmethod
    def is_available(cls) -> bool:
        success, _, _ = cls._execute("version")
        return success


class BrewPackageManager(PackageManager):
    """Package manager for Homebrew (macOS, Linux)."""

    SUPPORTED_OS = [OSType.MACOS, OSType.DEBIAN, OSType.UBUNTU]
    SUPPORTS_BATCH = True

    COMMANDS = {
        "version": ["brew", "--version"],
        "check": ["brew", "list", "--formula", "%arg0%"],
        "install": ["brew", "install", "%arg0%"],
        "batch_install": ["brew", "install", "%args%"],
    }

    @classmethod
    def is_available(cls) -> bool:
        success, _, _ = cls._execute("version")
        return success


class WinGetPackageManager(PackageManager):
    """Package manager for WinGet (Windows)."""

    SUPPORTED_OS = [OSType.WINDOWS]

    COMMANDS = {
        "version": ["winget", "--version"],
        "check": ["winget", "list", "--id", "%arg0%"],
        "install": [
            "winget",
            "install",
            "--id",
            "%arg0%",
            "--accept-source-agreements",
            "--accept-package-agreements",
        ],
    }

    @classmethod
    def is_available(cls) -> bool:
        success, _, _ = cls._execute("version")
        return success


class ChocolateyPackageManager(PackageManager):
    """Package manager for Chocolatey (Windows)."""

    SUPPORTED_OS = [OSType.WINDOWS]
    SUPPORTS_BATCH = True

    COMMANDS = {
        "version": ["choco", "--version"],
        "check": ["choco", "list", "--local-only", "%arg0%"],
        "install": ["choco", "install", "%arg0%", "-y"],
        "batch_install": ["choco", "install", "%args%", "-y"],
    }

    @classmethod
    def is_available(cls) -> bool:
        success, _, _ = cls._execute("version")
        return success

    @classmethod
    def _is_package_in_output(cls, package_name: str, output: str) -> bool:
        return f"{package_name} " in output.lower()


# Registry of available package managers
PACKAGE_MANAGERS = {
    "apt": APTPackageManager,
    "snap": SnapPackageManager,
    "brew": BrewPackageManager,
    "winget": WinGetPackageManager,
    "chocolatey": ChocolateyPackageManager,
}


def get_available_package_managers() -> Dict[str, Type[PackageManager]]:
    """
    Get all available package managers for the current system.

    Returns:
        Dict mapping package manager names to their classes
    """
    os_type = get_os_type()
    available_managers = {}

    for name, manager_cls in PACKAGE_MANAGERS.items():
        if manager_cls.supports_os(os_type) and manager_cls.is_available():
            available_managers[name] = manager_cls

    return available_managers


class DependencyFactory:
    """Factory class for creating dependencies with different configurations."""

    @staticmethod
    def create_system_dependency(
        name: str,
        friendly_name: Optional[str] = None,
        optional: bool = False,
        reason: str = "None specified.",
        **package_mappings,
    ) -> SYS_Dependency:
        """
        Create a system dependency with mappings for multiple package managers.

        Args:
            name: Name of the dependency
            friendly_name: User-friendly name (defaults to name if not provided)
            optional: Whether the dependency is optional
            reason: Reason for the dependency
            **package_mappings: Package names mapped to package manager names
                (e.g., apt="package-name", brew="brew-package")

        Returns:
            SYS_Dependency: Configured system dependency
        """
        mappings = []

        for manager, pkg_name in package_mappings.items():
            if pkg_name:
                mappings.append(
                    SystemPackageMapping(manager=manager, package_name=pkg_name)
                )

        return SYS_Dependency(
            name=name,
            friendly_name=friendly_name or name,
            optional=optional,
            reason=reason,
            package_mappings=mappings,
        )

    @staticmethod
    def create_pip_dependency(
        name: str,
        friendly_name: Optional[str] = None,
        optional: bool = False,
        reason: str = "None specified.",
        semver: Optional[str] = None,
    ) -> PIP_Dependency:
        """
        Create a PIP dependency.

        Args:
            name: Name of the dependency
            friendly_name: User-friendly name (defaults to name if not provided)
            optional: Whether the dependency is optional
            reason: Reason for the dependency
            semver: Semantic version requirement

        Returns:
            PIP_Dependency: Configured PIP dependency
        """
        return PIP_Dependency(
            name=name,
            friendly_name=friendly_name or name,
            optional=optional,
            reason=reason,
            semver=semver,
        )


# Static methods for SYS_Dependency to make creation more convenient
@staticmethod
def for_apt(name: str, package: str, **kwargs) -> "SYS_Dependency":
    """Create a dependency for APT package manager."""
    return DependencyFactory.create_system_dependency(name=name, apt=package, **kwargs)


@staticmethod
def for_brew(name: str, package: str, **kwargs) -> "SYS_Dependency":
    """Create a dependency for Homebrew package manager."""
    return DependencyFactory.create_system_dependency(name=name, brew=package, **kwargs)


@staticmethod
def for_winget(name: str, package: str, **kwargs) -> "SYS_Dependency":
    """Create a dependency for WinGet package manager."""
    return DependencyFactory.create_system_dependency(
        name=name, winget=package, **kwargs
    )


@staticmethod
def for_chocolatey(name: str, package: str, **kwargs) -> "SYS_Dependency":
    """Create a dependency for Chocolatey package manager."""
    return DependencyFactory.create_system_dependency(
        name=name, chocolatey=package, **kwargs
    )


@staticmethod
def for_snap(name: str, package: str, **kwargs) -> "SYS_Dependency":
    """Create a dependency for Snap package manager."""
    return DependencyFactory.create_system_dependency(name=name, snap=package, **kwargs)


@staticmethod
def for_all_platforms(
    name: str,
    apt_pkg: Optional[str] = None,
    brew_pkg: Optional[str] = None,
    winget_pkg: Optional[str] = None,
    chocolatey_pkg: Optional[str] = None,
    snap_pkg: Optional[str] = None,
    **kwargs,
) -> "SYS_Dependency":
    """Create a dependency with mappings for all supported platforms."""
    return DependencyFactory.create_system_dependency(
        name=name,
        apt=apt_pkg,
        brew=brew_pkg,
        winget=winget_pkg,
        chocolatey=chocolatey_pkg,
        snap=snap_pkg,
        **kwargs,
    )


# Add static methods to SYS_Dependency class
SYS_Dependency.for_apt = for_apt
SYS_Dependency.for_brew = for_brew
SYS_Dependency.for_winget = for_winget
SYS_Dependency.for_chocolatey = for_chocolatey
SYS_Dependency.for_snap = for_snap
SYS_Dependency.for_all_platforms = for_all_platforms


def install_system_dependencies(
    dependencies: List[SYS_Dependency], only_missing: bool = True
) -> Dict[str, bool]:
    """
    Install system dependencies based on the detected operating system.
    Uses dependency resolution to determine installation order.

    Args:
        dependencies: List of SYS_Dependency objects
        only_missing: Only install dependencies that are not already satisfied

    Returns:
        Dict mapping dependency names to whether they were successfully installed
    """
    if not dependencies:
        return {}

    # Convert list to dictionary for dependency resolution
    deps_dict = {dep.name: dep for dep in dependencies}

    # Resolve dependencies to get proper installation order
    try:
        resolved_deps = resolve_dependencies(deps_dict)
        # Convert back to list but in resolved order
        dependencies = list(resolved_deps.values())
        logging.info(
            f"Resolved dependencies in order: {[dep.name for dep in dependencies]}"
        )
    except DependencyResolutionError as e:
        logging.warning(
            f"Dependency resolution failed: {str(e)}. Using original order."
        )

    os_type = get_os_type()

    # Handle different OS types
    if os_type == OSType.DEBIAN or os_type == OSType.UBUNTU:
        return _install_apt_dependencies(dependencies, only_missing)
    elif os_type == OSType.MACOS:
        return _install_brew_dependencies(dependencies, only_missing)
    elif os_type == OSType.WINDOWS:
        return _install_winget_dependencies(dependencies, only_missing)
    else:
        logging.warning(
            f"Unsupported OS type for system dependency installation: {os_type}"
        )
        return {dep.name: False for dep in dependencies}


def _install_apt_dependencies(
    dependencies: List[SYS_Dependency], only_missing: bool = True
) -> Dict[str, bool]:
    """
    Install APT dependencies on Debian-based systems.

    Args:
        dependencies: List of SYS_Dependency objects
        only_missing: Only install dependencies that are not already satisfied

    Returns:
        Dict mapping dependency names to whether they were successfully installed
    """
    # Filter dependencies with apt packages
    apt_dependencies = []
    for dep in dependencies:
        apt_pkg = None
        # First try to find via package_mappings
        for mapping in dep.package_mappings:
            if mapping.manager == "apt":
                apt_pkg = mapping.package_name
                break

        # If not found and it has an apt_package attribute, use that
        if (
            apt_pkg is None
            and hasattr(dep, "apt_package")
            and dep.apt_package is not None
        ):
            apt_pkg = dep.apt_package

        if apt_pkg is not None:
            apt_dependencies.append((dep, apt_pkg))

    if not apt_dependencies:
        return {}

    # Check if we have sudo privileges
    try:
        subprocess.run(["sudo", "-n", "true"], capture_output=True, check=False)
        has_sudo = True
    except (FileNotFoundError, subprocess.SubprocessError):
        has_sudo = False

    # Determine which dependencies to install
    to_install = []
    deps_to_check = [dep for dep, _ in apt_dependencies]

    if only_missing:
        dependency_status = check_system_dependencies(deps_to_check)
        to_install = [
            (dep, pkg_name)
            for dep, pkg_name in apt_dependencies
            if not dependency_status.get(dep.name, False)
        ]
    else:
        to_install = apt_dependencies

    if not to_install:
        return {}

    # Install dependencies
    result = {}
    for dep, _ in apt_dependencies:
        result[dep.name] = False  # Initialize all as False

    if has_sudo:
        try:
            # Update package lists
            subprocess.run(["sudo", "apt-get", "update", "-qq"], check=True)

            # Install all packages in one command for efficiency
            pkg_names = [pkg_name for _, pkg_name in to_install]
            install_cmd = ["sudo", "apt-get", "install", "-y"] + pkg_names
            install_result = subprocess.run(
                install_cmd, capture_output=True, text=True, check=False
            )

            if install_result.returncode == 0:
                for dep, pkg_name in to_install:
                    result[dep.name] = True
                    logging.info(f"Successfully installed APT package: {pkg_name}")
            else:
                # If batch install fails, try individually
                for dep, pkg_name in to_install:
                    pkg_result = subprocess.run(
                        ["sudo", "apt-get", "install", "-y", pkg_name],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    result[dep.name] = pkg_result.returncode == 0
                    if result[dep.name]:
                        logging.info(f"Successfully installed APT package: {pkg_name}")
                    else:
                        logging.error(
                            f"Failed to install APT package {pkg_name}: {pkg_result.stderr}"
                        )
        except Exception as e:
            logging.error(f"Error installing APT dependencies: {str(e)}")
    else:
        logging.warning("Cannot install APT dependencies without sudo privileges")

    return result


def _install_brew_dependencies(
    dependencies: List[SYS_Dependency], only_missing: bool = True
) -> Dict[str, bool]:
    """
    Install Homebrew dependencies on macOS systems.

    Args:
        dependencies: List of SYS_Dependency objects
        only_missing: Only install dependencies that are not already satisfied

    Returns:
        Dict mapping dependency names to whether they were successfully installed
    """
    # Filter dependencies with brew packages
    brew_dependencies = []
    for dep in dependencies:
        brew_pkg = None
        # First try to find via package_mappings
        for mapping in dep.package_mappings:
            if mapping.manager == "brew":
                brew_pkg = mapping.package_name
                break

        # If not found and it's a BREW_Dependency, try the brew_package attribute
        if (
            brew_pkg is None
            and hasattr(dep, "brew_package")
            and dep.brew_package is not None
        ):
            brew_pkg = dep.brew_package

        if brew_pkg is not None:
            brew_dependencies.append((dep, brew_pkg))

    if not brew_dependencies:
        return {}

    # Determine which dependencies to install
    to_install = []
    deps_to_check = [dep for dep, _ in brew_dependencies]

    if only_missing:
        dependency_status = check_system_dependencies(deps_to_check)
        to_install = [
            (dep, pkg_name)
            for dep, pkg_name in brew_dependencies
            if not dependency_status.get(dep.name, False)
        ]
    else:
        to_install = brew_dependencies

    if not to_install:
        return {}

    # Install dependencies
    result = {}
    for dep, _ in brew_dependencies:
        result[dep.name] = False  # Initialize all as False

    try:
        # Try to install all packages in one command for efficiency
        pkg_names = [pkg_name for _, pkg_name in to_install]
        install_cmd = ["brew", "install"] + pkg_names
        install_result = subprocess.run(
            install_cmd, capture_output=True, text=True, check=False
        )

        if install_result.returncode == 0:
            for dep, pkg_name in to_install:
                result[dep.name] = True
                logging.info(f"Successfully installed Homebrew package: {pkg_name}")
        else:
            # If batch install fails, try individually
            for dep, pkg_name in to_install:
                pkg_result = subprocess.run(
                    ["brew", "install", pkg_name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                result[dep.name] = pkg_result.returncode == 0
                if result[dep.name]:
                    logging.info(f"Successfully installed Homebrew package: {pkg_name}")
                else:
                    logging.error(
                        f"Failed to install Homebrew package {pkg_name}: {pkg_result.stderr}"
                    )
    except FileNotFoundError:
        logging.error("Homebrew (brew) not found; cannot install dependencies")
    except Exception as e:
        logging.error(f"Error installing Homebrew dependencies: {str(e)}")

    return result


def _install_winget_dependencies(
    dependencies: List[SYS_Dependency], only_missing: bool = True
) -> Dict[str, bool]:
    """
    Install WinGet dependencies on Windows systems.

    Args:
        dependencies: List of SYS_Dependency objects
        only_missing: Only install dependencies that are not already satisfied

    Returns:
        Dict mapping dependency names to whether they were successfully installed
    """
    # Filter dependencies with winget packages
    winget_dependencies = []
    for dep in dependencies:
        winget_pkg = None
        # First try to find via package_mappings
        for mapping in dep.package_mappings:
            if mapping.manager == "winget":
                winget_pkg = mapping.package_name
                break

        # If not found and it's a WINGET_Dependency, try the winget_package attribute
        if (
            winget_pkg is None
            and hasattr(dep, "winget_package")
            and dep.winget_package is not None
        ):
            winget_pkg = dep.winget_package

        if winget_pkg is not None:
            winget_dependencies.append((dep, winget_pkg))

    if not winget_dependencies:
        return {}

    # Determine which dependencies to install
    to_install = []
    deps_to_check = [dep for dep, _ in winget_dependencies]

    if only_missing:
        dependency_status = check_system_dependencies(deps_to_check)
        to_install = [
            (dep, pkg_name)
            for dep, pkg_name in winget_dependencies
            if not dependency_status.get(dep.name, False)
        ]
    else:
        to_install = winget_dependencies

    if not to_install:
        return {}

    # Install dependencies
    result = {}
    for dep, _ in winget_dependencies:
        result[dep.name] = False  # Initialize all as False

    try:
        # WinGet doesn't support installing multiple packages in one command efficiently
        # So we'll install them one by one
        for dep, pkg_name in to_install:
            # Note: --accept-source-agreements is needed to bypass prompts
            pkg_result = subprocess.run(
                [
                    "winget",
                    "install",
                    "--id",
                    pkg_name,
                    "--accept-source-agreements",
                    "--accept-package-agreements",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            result[dep.name] = pkg_result.returncode == 0
            if result[dep.name]:
                logging.info(f"Successfully installed WinGet package: {pkg_name}")
            else:
                logging.error(
                    f"Failed to install WinGet package {pkg_name}: {pkg_result.stderr}"
                )
    except FileNotFoundError:
        logging.error("WinGet not found; cannot install dependencies")
    except Exception as e:
        logging.error(f"Error installing WinGet dependencies: {str(e)}")

    return result


def check_pip_dependencies(dependencies: List[PIP_Dependency]) -> Dict[str, bool]:
    """
    Check if PIP dependencies are satisfied.

    Args:
        dependencies: List of PIP_Dependency objects

    Returns:
        Dict mapping dependency names to whether they are satisfied
    """
    result = {}
    for dep in dependencies:
        result[dep.name] = dep.is_satisfied()
        if not result[dep.name] and not dep.optional:
            logging.warning(f"Required PIP dependency '{dep.name}' is not installed")

    return result


def install_pip_dependencies(
    dependencies: List[PIP_Dependency], only_missing: bool = True
) -> Dict[str, bool]:
    """
    Install PIP dependencies based on resolved dependency order.

    Args:
        dependencies: List of PIP_Dependency objects
        only_missing: Only install dependencies that are not already satisfied

    Returns:
        Dict mapping dependency names to whether they were successfully installed
    """
    if not dependencies:
        return {}

    # Convert list to dictionary for dependency resolution
    deps_dict = {dep.name: dep for dep in dependencies}

    # Resolve dependencies to get proper installation order
    try:
        resolved_deps = resolve_dependencies(deps_dict)
        # Convert back to list but in resolved order
        dependencies = list(resolved_deps.values())
        logging.info(
            f"Resolved PIP dependencies in order: {[dep.name for dep in dependencies]}"
        )
    except DependencyResolutionError as e:
        logging.warning(
            f"Dependency resolution failed: {str(e)}. Using original order."
        )

    # Determine which dependencies to install
    to_install = []
    if only_missing:
        dependency_status = check_pip_dependencies(dependencies)
        to_install = []
        for dep in dependencies:
            if not dependency_status.get(dep.name, False):
                # Include version requirement if specified
                if dep.semver:
                    to_install.append((dep.name, f"{dep.name}{dep.semver}"))
                else:
                    to_install.append((dep.name, dep.name))
    else:
        to_install = []
        for dep in dependencies:
            if dep.semver:
                to_install.append((dep.name, f"{dep.name}{dep.semver}"))
            else:
                to_install.append((dep.name, dep.name))

    if not to_install:
        return {}

    # Install dependencies
    result = {}

    # Get package specs for installation
    pkg_specs = [spec for _, spec in to_install]

    try:
        # Try batch installation first
        pip_cmd = [sys.executable, "-m", "pip", "install"] + pkg_specs
        install_result = subprocess.run(
            pip_cmd, capture_output=True, text=True, check=False
        )

        if install_result.returncode == 0:
            # All packages installed successfully
            for name, _ in to_install:
                result[name] = True
                logging.info(f"Successfully installed PIP package: {name}")
        else:
            # If batch install fails, try individually
            for name, spec in to_install:
                pkg_result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", spec],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                result[name] = pkg_result.returncode == 0
                if result[name]:
                    logging.info(f"Successfully installed PIP package: {spec}")
                else:
                    logging.error(
                        f"Failed to install PIP package {spec}: {pkg_result.stderr}"
                    )
    except Exception as e:
        logging.error(f"Error installing PIP dependencies: {str(e)}")
        for name, _ in to_install:
            result[name] = False

    return result


# Define dependency resolution classes
class DependencyResolutionError(Exception):
    """Exception raised for errors in the dependency resolution process."""

    pass


class DependencyNode:
    """A node in the dependency graph representing a dependency."""

    def __init__(self, name: str, version: str = "0.0.0"):
        self.name = name
        self.version = version
        self.dependencies: Dict[str, str] = {}  # name -> version_constraint

    def add_dependency(self, name: str, version_constraint: Optional[str] = None):
        """Add a dependency to this node."""
        self.dependencies[name] = version_constraint

    def __repr__(self):
        return f"<DependencyNode {self.name}@{self.version}>"


class DependencyProvider(AbstractProvider):
    """Provider for resolvelib that handles dependency resolution."""

    def __init__(self, dependency_map: Dict[str, List[DependencyNode]]):
        """
        Initialize with a mapping of dependency name to available versions.

        Args:
            dependency_map: Dict mapping dependency names to lists of DependencyNode objects
        """
        self.dependency_map = dependency_map

    def identify(self, requirement_or_candidate):
        """Get the name of the dependency."""
        if hasattr(requirement_or_candidate, "name"):
            return requirement_or_candidate.name
        # If it's just a string, return it as is
        return requirement_or_candidate

    def get_preference(
        self, identifier, resolutions, candidates, information, backtrack_causes
    ):
        """Get the preference for a dependency (higher versions preferred)."""
        return len(candidates)

    def find_matches(self, identifier, requirements, incompatibilities):
        """Find candidates matching the requirements."""
        if identifier not in self.dependency_map:
            return []

        candidates = []
        for candidate in self.dependency_map[identifier]:
            # Check if candidate is compatible with all requirements
            compatible = True
            for req in requirements:
                # Handle both DependencyRequirement objects and string/name-only requirements
                version_constraint = getattr(req, "version_constraint", None)
                if not self._check_version_compatibility(
                    candidate.version, version_constraint
                ):
                    compatible = False
                    break

            if compatible:
                candidates.append(candidate)

        # Sort by version (higher versions first)
        candidates.sort(key=lambda c: c.version, reverse=True)
        return candidates

    def is_satisfied_by(self, requirement, candidate):
        """Check if a candidate satisfies a requirement."""
        # Handle both DependencyRequirement objects and string/name-only requirements
        version_constraint = getattr(requirement, "version_constraint", None)
        return self._check_version_compatibility(candidate.version, version_constraint)

    def get_dependencies(self, candidate):
        """Get dependencies of a candidate."""
        return [
            DependencyRequirement(name, version_constraint)
            for name, version_constraint in candidate.dependencies.items()
        ]

    def _check_version_compatibility(
        self, version: str, version_constraint: Optional[str]
    ) -> bool:
        """
        Check if a version is compatible with a constraint.

        Args:
            version: Version to check
            version_constraint: Version constraint string (e.g., ">=1.0.0")

        Returns:
            bool: True if compatible
        """
        if not version_constraint:
            return True

        try:
            import semver

            return semver.match(version, version_constraint)
        except (ImportError, ValueError):
            # If we can't check, assume compatible
            return True


class DependencyRequirement:
    """Represents a requirement for resolvelib."""

    def __init__(self, name: str, version_constraint: Optional[str] = None):
        self.name = name
        self.version_constraint = version_constraint

    def __repr__(self):
        if self.version_constraint:
            return f"<Requirement {self.name}{self.version_constraint}>"
        return f"<Requirement {self.name}>"


class BaseReporter:
    """Basic reporter implementation for resolvelib."""

    def starting(self):
        pass

    def starting_round(self, index):
        pass

    def ending_round(self, index, state):
        pass

    def ending(self, state):
        pass

    def adding_requirement(self, requirement, parent):
        pass

    def backtracking(self, causes):
        pass

    def pinning(self, candidate):
        pass


def resolve_dependencies(dependencies: Dict[str, Dependency]) -> Dict[str, Dependency]:
    """
    Resolve dependencies using resolvelib.

    Args:
        dependencies: Dict mapping dependency names to Dependency objects

    Returns:
        Dict[str, Dependency]: Resolved dependencies in installation order

    Raises:
        DependencyResolutionError: If resolution fails
    """
    if not HAS_RESOLVELIB:
        logging.warning(
            "resolvelib not installed, skipping complex dependency resolution."
        )
        return dependencies

    # Build dependency nodes
    dependency_map: Dict[str, List[DependencyNode]] = {}

    # Create nodes for all dependencies
    for name, dep in dependencies.items():
        if name not in dependency_map:
            dependency_map[name] = []

        # Create a node for this dependency
        node = DependencyNode(name)

        # Add its dependencies based on the dependency type
        if isinstance(dep, SYS_Dependency):
            # System dependencies might have other system dependencies
            # For now, we don't model these, but we could extend this
            pass
        elif isinstance(dep, PIP_Dependency):
            # For PIP dependencies, we can use their declared versions
            pass

        dependency_map[name].append(node)

    # Create provider and resolver
    provider = DependencyProvider(dependency_map)

    try:
        resolver = Resolver(provider, BaseReporter())

        # Create initial requirements
        requirements = [DependencyRequirement(name) for name in dependencies.keys()]

        # Resolve
        result = resolver.resolve(requirements)

        # Construct result in resolution order
        resolved_deps = {}
        for node in result.mapping.values():
            resolved_deps[node.name] = dependencies[node.name]

        return resolved_deps

    except Exception as e:
        # If we get an exception, log it and fall back to original dependencies
        logging.error(f"Dependency resolution failed: {str(e)}")
        raise DependencyResolutionError(f"Failed to resolve dependencies: {str(e)}")
