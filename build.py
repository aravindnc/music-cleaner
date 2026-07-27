import re
import sys
import subprocess

def bump_version():
    """Auto-increment patch version in version.py and file_version_info.txt before build."""
    with open("version.py", "r") as f:
        content = f.read()

    match = re.search(r'__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"', content)
    if not match:
        print("Could not find version pattern in version.py")
        sys.exit(1)

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3)) + 1
    new_version = f"{major}.{minor}.{patch}"

    # 1. Update version.py
    with open("version.py", "w") as f:
        f.write(f'# Version definition\n__version__ = "{new_version}"\n')
    print(f"Updated version.py -> v{new_version}")

    # 2. Update file_version_info.txt
    if sys.platform == "win32":
        info_content = f"""# VSVersionInfo file for Windows PyInstaller executable metadata
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
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
          u'040904B0',
          [
            StringStruct(u'CompanyName', u'aravindnc.com'),
            StringStruct(u'FileDescription', u'MusicCleaner - Rapidly review, keep, or delete thousands of MP3s'),
            StringStruct(u'FileVersion', u'{new_version}'),
            StringStruct(u'InternalName', u'MusicCleaner'),
            StringStruct(u'LegalCopyright', u'Copyright (c) 2026 aravindnc.com'),
            StringStruct(u'OriginalFilename', u'MusicCleaner_v{new_version}.exe'),
            StringStruct(u'ProductName', u'MusicCleaner (Fast Song Reviewer)'),
            StringStruct(u'ProductVersion', u'{new_version}.0')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
        with open("file_version_info.txt", "w") as f:
            f.write(info_content)
        print("Updated file_version_info.txt")

    # 3. Trigger PyInstaller build
    exe_name = f"MusicCleaner_v{new_version}"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--icon=app_icon.ico",
        "--add-data", "app_icon.ico;.",
        "--version-file=file_version_info.txt",
        f"--name={exe_name}",
        "main.py"
    ]
    print(f"\nBuilding executable for v{new_version}...")
    subprocess.run(cmd, check=True)
    print(f"\n[OK] Successfully built dist/{exe_name}.exe (v{new_version})")

if __name__ == "__main__":
    bump_version()
