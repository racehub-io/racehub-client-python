import subprocess
import os
import sys

# Paths to scripts and files
update_version_script = r"build_scripts\update_iss_version.py"
generate_version_files_script = r"build_scripts\generate_version_files.py"
iss_file = r"setup.iss" 
inno_setup_compiler = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

# Helper to run a script or command and handle errors
def run_command(command, description):
    try:
        print(f"Running: {description}")
        subprocess.run(command, check=True, shell=True)
        print(f"Finished: {description}\n")
    except subprocess.CalledProcessError as e:
        print(f"Error while running {description}: {e}")
        sys.exit(1)

# Run update_iss_version.py
run_command(f"python {update_version_script}", "update_iss_version.py")

# Run generate_version_files.py
run_command(f"python {generate_version_files_script}", "generate_version_files.py")

# Build executables with PyInstaller
run_command("pyinstaller client.spec", "building client executable")
run_command("pyinstaller worker.spec", "building worker executable")

# Compile setup.iss
if not os.path.exists(iss_file):
    print(f"Error: {iss_file} not found!")
    sys.exit(1)

run_command(f'"{inno_setup_compiler}" "{iss_file}"', "compiling setup.iss")

print("Build process completed successfully!")
