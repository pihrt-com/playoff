# test.py – jednoduché testy pro usb_module.py
import time
from usb_module import USBManager, PY_SERIAL_AVAILABLE

print("=== TEST USB MODULE ===")

# 1) Kontrola zda je pyserial vůbec dostupný
if not PY_SERIAL_AVAILABLE:
    print("pyserial není dostupný – instaluj: pip install pyserial")
    exit(1)

# 2) Vytvoříme instanci USBManager
um = USBManager(verbose=True, prevent_reset=True)

# 3) Najdeme dostupné porty
ports = um.list_ports()
print(f"Dostupné porty: {ports}")

if not ports:
    print("ŽÁDNÉ PORTY NENALEZENY – připoj zařízení a spusť test znovu.")
    exit(1)

# Vybere druhý nalezený port
port = ports[1]
print(f"Použiji port: {port}")

# Nastavíme port/baud/timeout
um.validate_and_set(port, 9600, 2.0)


# === TEST 1: Otevření portu a zavření ===
print("\n--- TEST 1: OPEN/CLOSE ---")
try:
    um.handler.open(port=port)
    print("OPEN OK")
    um.handler.close()
    print("CLOSE OK")
except Exception as e:
    print("OPEN/CLOSE FAIL:", e)
    exit(1)


# === TEST 2: SYNCHRONNÍ START ===
print("\n--- TEST 2: send_start_sync ---")
ok, reason = um.send_start_sync()
print(f"Výsledek: ok={ok}, reason={reason}")


# === TEST 3: ASYNCHRONNÍ START ===
print("\n--- TEST 3: send_start_async ---")

done = False
result = None

def on_result(ok, reason):
    global done, result
    print(f"[callback] Výsledek: ok={ok}, reason={reason}")
    result = (ok, reason)
    done = True

thread = um.send_start_async(on_result)

# počkáme max 3 sekundy na callback
timeout = time.time() + 3
while not done and time.time() < timeout:
    time.sleep(0.05)

if not done:
    print("ASYNCHRONNÍ TEST: TIMEOUT – callback se neozval.")
else:
    print("ASYNCHRONNÍ TEST proběhl.")


print("\n=== HOTOVO ===")
