import subprocess
import sys
import os

app_dir = os.path.dirname(os.path.abspath(__file__))

updater_path = os.path.join(app_dir, "updater.exe")
target_exe = os.path.join(app_dir, "Playoff.exe")

download_url = "https://github.com/pihrt-com/playoff/releases/download/1.0.3/PlayoffSetup_1.0.3.exe"

print("Spouštím updater...")
print("Updater:", updater_path)
print("Cíl:", target_exe)
print("URL:", download_url)

subprocess.Popen([
    updater_path,
    target_exe,
    download_url
])

print("Updater spuštěn, aplikace se nyní ukončí.")
sys.exit(0)
