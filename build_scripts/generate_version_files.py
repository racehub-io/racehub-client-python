import os
import sys

# Resolve paths relative to the current script's location
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.join(script_dir, "..")
sys.path.insert(0, parent_dir)

from racehub_client_python import __version__

output_dir = os.path.join(parent_dir, "racehub_client_python")

product_names = ["RaceHubClient", "RaceHubWorker"]

for product_name in product_names:
    version_tuple = tuple(map(int, __version__.split("."))) + (0,)
    output_file = os.path.join(output_dir, f"{product_name.lower()}_version.txt")
    with open(output_file, "w") as f:
        f.write(
            f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', 'RaceCloud, Ltd.'),
            StringStruct('FileDescription', '{product_name}'),
            StringStruct('FileVersion', '{__version__}'),
            StringStruct('InternalName', '{product_name}'),
            StringStruct('ProductName', '{product_name}'),
            StringStruct('ProductVersion', '{__version__}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)"""
        )

print(f"Version files created for: {', '.join(product_names)}")
