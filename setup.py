"""py2app build configuration for AudioBoost."""

from setuptools import setup

APP = ["src/main.py"]
DATA_FILES = [("assets", ["src/assets/icon.icns"])]
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "src/assets/icon.icns",
    "plist": {
        "CFBundleName": "AudioBoost",
        "CFBundleDisplayName": "AudioBoost",
        "CFBundleIdentifier": "com.olanetsoft.audioboost",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "NSHumanReadableCopyright": "© 2026 Idris Olubisi",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "MPEG-4 Video",
                "CFBundleTypeRole": "Editor",
                "LSItemContentTypes": ["public.mpeg-4"],
                "LSHandlerRank": "Alternate",
            }
        ],
    },
    "packages": ["tkinterdnd2"],
    "includes": ["tkinter"],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
