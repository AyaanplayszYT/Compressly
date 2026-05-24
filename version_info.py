"""Generate a PyInstaller version info file for the Windows PE header.

Having proper version info reduces antivirus false positives because:
  1. AV engines flag unsigned executables with no version info more aggressively.
  2. Version info proves the exe was intentionally built, not injected.
  3. The company name / product name appear in Windows security dialogs.
"""

from __future__ import annotations

from pathlib import Path

VERSION_INFO = """
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [
          StringStruct(u'CompanyName',      u'Mistix'),
          StringStruct(u'FileDescription',  u'Compressly - Modern Image Optimization'),
          StringStruct(u'FileVersion',      u'1.0.0.0'),
          StringStruct(u'InternalName',     u'Compressly'),
          StringStruct(u'LegalCopyright',   u'Copyright (c) 2026 Mistix'),
          StringStruct(u'OriginalFilename', u'Compressly.exe'),
          StringStruct(u'ProductName',      u'Compressly'),
          StringStruct(u'ProductVersion',   u'1.0.0.0'),
        ]
      )
    ]),
    VarFileInfo([VarStruct(u'Translation', [0x0409, 1200])])
  ]
)
"""

if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "version_info.txt"
    out.write_text(VERSION_INFO.strip(), encoding="utf-8")
    print(f"Wrote {out}")
