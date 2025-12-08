import sys
import os
import urllib.request
import tempfile
import subprocess

print("=== Playoff Installer Updater ===")

if len(sys.argv) < 3:
    print("Použití:")
    print("updater.exe <target_exe> <installer_url>")
    sys.exit(1)

target_exe = sys.argv[1]
installer_url = sys.argv[2]

print("Cílová aplikace:", target_exe)
print("URL instalátoru:", installer_url)

tmp_dir = tempfile.gettempdir()
installer_path = os.path.join(tmp_dir, "PlayoffSetup_update.exe")

try:
    print("Stahuji instalátor...")
    urllib.request.urlretrieve(installer_url, installer_path)
    print("Staženo do:", installer_path)
except Exception as e:
    print("CHYBA při stahování:", e)
    input("Stiskni Enter pro ukončení...")
    sys.exit(2)

print("Spouštím instalátor...")

try:
    subprocess.Popen(
        [installer_path],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    )
except Exception as e:
    print("CHYBA při spouštění instalátoru:", e)
    input("Stiskni Enter pro ukončení...")
    sys.exit(3)

print("Updater hotov — instalátor běží.")
sys.exit(0)
