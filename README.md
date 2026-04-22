# Jianying Beat Auto-Cut

An automated video editing tool that cuts video materials according to music beats and generates Jianying (CapCut) draft files.

## Features

- Upload multiple video materials at once
- Upload multiple audio tracks at once
- Process with "per-beat cut" strategy
- Generate independent Jianying draft for each audio track
- Desktop app + Web app dual mode

## Desktop App (Recommended)

Double-click `start_desktop_app.bat` to open the desktop window.

## Web App

```powershell
python jianying_autocut_webapp.py
```

Then open http://127.0.0.1:5000

## Build EXE

```powershell
.\build_desktop_exe.bat
```

## License
MIT
