import csv
import json
import socket
import time
from pathlib import Path
from datetime import datetime

SERVER = ("10.0.0.2", 5005)
DURATION = 90
INTERVAL = 0.1
TIMEOUT = 0.15

OUTPUT = Path(__file__).resolve().parents[1] / "results" / "latest_failure_recovery.csv"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.settimeout(TIMEOUT)

start_time = time.time()
sequence = 0
results = []

print("Starting continuous UDP failure-recovery probe")
print(f"Duration: {DURATION} seconds")
print(f"Interval: {INTERVAL} seconds")

while time.time() - start_time < DURATION:
    sequence += 1

    packet = {
        "sequence": sequence,
        "timestamp": time.time()
    }

    sent_at = time.perf_counter()

    try:
        client.sendto(json.dumps(packet).encode(), SERVER)
        data, _ = client.recvfrom(4096)

        received_at = time.perf_counter()
        response = json.loads(data.decode())

        success = response.get("sequence") == sequence
        rtt = (received_at - sent_at) * 1000 if success else None

    except socket.timeout:
        success = False
        rtt = None

    elapsed = time.time() - start_time

    results.append({
        "sequence": sequence,
        "elapsed_seconds": round(elapsed, 3),
        "status": "received" if success else "timeout",
        "rtt_ms": round(rtt, 3) if rtt is not None else ""
    })

    if success:
        print(f"Packet {sequence}: RECEIVED | RTT {rtt:.3f} ms")
    else:
        print(f"Packet {sequence}: TIMEOUT")

    time.sleep(INTERVAL)

client.close()

with open(OUTPUT, "w", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "sequence",
            "elapsed_seconds",
            "status",
            "rtt_ms"
        ]
    )
    writer.writeheader()
    writer.writerows(results)

received = sum(r["status"] == "received" for r in results)
lost = len(results) - received

print("\n========== FAILURE RECOVERY RESULTS ==========")
print(f"Packets sent     : {len(results)}")
print(f"Packets received : {received}")
print(f"Packets lost     : {lost}")
print(f"Packet loss      : {lost / len(results) * 100:.2f}%")
print(f"Probe duration   : {DURATION} seconds")
print(f"CSV report       : {OUTPUT}")
