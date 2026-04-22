@echo off
cd /d %~dp0
python -m PyInstaller --noconfirm --clean --windowed --name JianyingAutoCutApp_v11 --collect-data pyJianYingDraft --collect-data pyJianYingDraft.assets jianying_autocut_desktop.py
echo.
echo Build done. EXE path: %~dp0dist\JianyingAutoCutApp_v11\JianyingAutoCutApp_v11.exe
pause
