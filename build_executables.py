import subprocess
import sys
from pathlib import Path


def build_executable(spec_file: str) -> bool:
    """
    Build an executable using PyInstaller

    Args:
        spec_file: Path to the spec file

    Returns:
        bool: True if build was successful, False otherwise
    """
    try:
        subprocess.run(["pyinstaller", spec_file], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error building {spec_file}: {e}")
        return False


def main():
    # Get the project root directory
    root_dir = Path(__file__).parent

    # Build client
    print("Building client...")
    if not build_executable("client.spec"):
        sys.exit(1)

    # Build worker
    print("\nBuilding worker...")
    if not build_executable("worker.spec"):
        sys.exit(1)

    print("\nBuild completed successfully!")


if __name__ == "__main__":
    main()
