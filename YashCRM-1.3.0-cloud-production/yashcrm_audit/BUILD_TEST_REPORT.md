# Yash CRM 1.1.0 — Build/Test Report

## Release changes
- Python runtime/build gate pinned to CPython 3.12. Python 3.14 is explicitly not selected or accepted.
- PyInstaller build embeds application icon and Windows version metadata.
- Added Inno Setup 6 installer definition and `build_installer.bat` for a normal Windows installation, Start Menu shortcut, optional Desktop shortcut, uninstall entry, and post-install launch.
- Frozen Windows builds store writable CRM data in `%LOCALAPPDATA%\\YashCRM\\data\\yashcrm.db` rather than beside the executable under Program Files.
- Lead conversion is transactional/idempotent and always creates or restores a linked Deal. Repeated conversion reuses the existing linked Account/Contact/Deal rather than duplicating them.
- Administrator/profile email is editable, validated, uniqueness-checked, and persisted.
- Added continuous subtle glossy motion to navigation and a slightly denser main background, with `prefers-reduced-motion` support.

## Verification performed in this environment
- `python -m py_compile`: PASS for `app/main.py`, `launch.py`, and `yashcrm_app.py`.
- Existing `scripts/check_contracts.py` against a live local Uvicorn server: PASS.
- Route smoke checks: PASS (200) for `/health`, `/`, `/dashboard`, `/leads`, `/contacts`, `/accounts`, `/deals`, `/products`, `/activities`, `/settings/general`, `/settings/profile-users`.
- Lead conversion integration check: PASS; a Deal was created and appeared through `/api/deals`; second conversion returned the same Deal ID; one matching Deal remained.
- Profile email integration check: PASS for valid persisted update; malformed email returned HTTP 422.
- Static dynamic-execution scan over application/launcher JS/Python: no `eval(`, `exec(`, `shell=True`, or `os.system(` matches.
- Source package contained no pre-existing `.exe`, `.msi`, `.iss`, or PyInstaller `.spec` binary artifact to inspect. The old packaging path was `build_exe.bat` only.

## Windows build/runtime limitation
This execution environment is Linux and does not provide Windows, Wine, Inno Setup (`ISCC.exe`), or a Windows CPython 3.12 toolchain. PyInstaller does not cross-compile a Windows executable from Linux. Therefore no Windows `.exe` or installer is included and no claim of Windows execution is made.

On Windows, install CPython 3.12 and Inno Setup 6, then run `build_installer.bat`. The script refuses a non-3.12 Python before building. The expected outputs are `dist\\YashCRM.exe` and `release\\YashCRM-Setup-1.1.0.exe`.

## Recommended final Windows release check
Run the installer on a clean Windows 10/11 VM, launch from Start Menu and Desktop, verify `%LOCALAPPDATA%\\YashCRM\\data\\yashcrm.db` is created, convert one lead twice and confirm only one linked deal exists, edit the administrator email and restart to confirm persistence, then scan/sign the installer before public distribution.
