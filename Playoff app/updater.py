# updater.py - Martin Pihrt Playoff auto-updater
import os, sys, urllib.request, shutil, time, tempfile

def download(url, dest):
    with urllib.request.urlopen(url, timeout=30) as r:
        with open(dest, "wb") as f:
            shutil.copyfileobj(r, f)

def replace(target, newfile):
    # rename old → .bak
    bak = target + ".bak"
    try:
        if os.path.exists(bak):
            os.remove(bak)
        if os.path.exists(target):
            os.rename(target, bak)
        os.rename(newfile, target)
        return True
    except Exception as e:
        print("ERROR:", e)
        return False

def main():
    if len(sys.argv) < 3:
        print("Usage: updater.exe <path_to_playoff.exe> <download_url>")
        sys.exit(1)

    target = sys.argv[1]
    url = sys.argv[2]

    fd, tmp = tempfile.mkstemp(suffix=".exe")
    os.close(fd)

    print("Downloading:", url)
    try:
        download(url, tmp)
    except Exception as e:
        print("Download error:", e)
        sys.exit(2)

    print("Replacing...")
    if replace(target, tmp):
        print("Update complete.")
        try:
            os.startfile(target)
        except:
            pass
        sys.exit(0)
    else:
        print("Update failed.")
        sys.exit(3)

if __name__ == "__main__":
    main()
