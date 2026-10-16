# RaceHub Python client

Recording, parsing, and local processing do not need a Firebase account.
Connect the web app to `ws://localhost:8082`.

Browser connections accept `http://localhost:3000` and `http://127.0.0.1:3000`.
Set `RACEHUB_ALLOWED_ORIGINS` to add trusted UI origins, separated by commas.
Use the exact scheme, host, and port. Wildcards do not match.
Native clients without an Origin header can connect from loopback.

## Build and Release Guide

## Installation

1. **Install Dependencies**  
   Use [Poetry](https://python-poetry.org/) to install project dependencies:
   ```bash
   poetry install
   ```

2. **Install Inno Setup**  
   Ensure you have [Inno Setup 6](https://jrsoftware.org/isdl.php) installed at:
   ```
   C:\Program Files (x86)\Inno Setup 6\ISCC.exe
   ```

---

## Build Process

### Run on Terminal
To build the executables, use the following commands:

- For both client and worker:
  ```bash
  python build_executables.py
  ```

- For the client only:
  ```bash
  pyinstaller client.spec
  ```

- For the worker only:
  ```bash
  pyinstaller worker.spec
  ```

---

### Generate a Release Version

1. **Update Version**  
   Update the version number in `racehub_client_python/__init__.py`.

2. **Add iRacing Server**  
   Copy `RaceHub-iRacing-Server.exe` to the project's root directory.

3. **Run the Build Script**  
   Generate the release version and installer by running:
   ```bash
   python build_release.py
   ```

4. **Output**  
   This process will create the updated installer.

Machine usage logging is off by default. Set `RACEHUB_MACHINE_USAGE_URL` to a service that you control to enable it.

## Community use

RaceHub source contributions are available under the scope in [LICENSING.md](LICENSING.md).
Local features do not require a RaceHub subscription.
Third-party games, SDKs, and optional hosting keep their own terms and costs.
See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
No hosted service or maintenance schedule is included.
