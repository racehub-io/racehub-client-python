import re
import os

# Resolve paths relative to the current script's location
script_dir = os.path.dirname(os.path.abspath(__file__))
init_file = os.path.join(script_dir, "../racehub_client_python/__init__.py")
iss_file = os.path.join(script_dir, "../setup.iss")

# Extract version from __init__.py
with open(init_file, "r") as f:
    content = f.read()
    match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    if not match:
        raise ValueError("Version not found in __init__.py")
    version = match.group(1)

# Update the .iss file
with open(iss_file, "r") as f:
    iss_content = f.read()

updated_iss_content = re.sub(r"#define MyAppVersion \".*?\"", f'#define MyAppVersion "{version}"', iss_content)

with open(iss_file, "w") as f:
    f.write(updated_iss_content)

print(f"Updated {iss_file} with version {version}")
