import csv
import json
import socket
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SERVER = ("10.0.0.2", 5005)
PORT_TIMEOUT = 1.0
PACKET_COUNT = 50
INTERVAL = 0.1
PATH = (sys.argv[1].lower() if len(sys.argv) > 1 else "lower")
if PATH not in ("upper", "lower"):
    raise SystemExit("Usage: udp_client.py [upper|lower]")
BASE = Path(__file__).resolve().parents[1]
RESULTS = BASE / "results"
RESULTS.mkdir(exist_ok=True)
JSON_FILE = RESULTS / "latest_comparison.json"
CSV_FILE = RESULTS / "latest_udp_measurements.csv"

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.settimeout(PORT_TIMEOUT)
rtts, rows = [], []
print(f"UDP Diagnostic Client -> {SERVER}; measuring {PATH.upper()} path")
for sequence in range(1, PACKET_COUNT + 1):
    packet = {"sequence": sequence, "timestamp": time.time()}
    started = time.perf_counter()
    status, rtt = "timeout", None
    try:
        client.sendto(json.dumps(packet).encode(), SERVER)
        data, _ = client.recvfrom(4096)
        response = json.loads(data.decode())
        if response.get("sequence") == sequence:
            rtt = (time.perf_counter() - started) * 1000
            rtts.append(rtt)
            status = "received"
            print(f"Packet {sequence:02d} | RTT: {rtt:.3f} ms")
    except (socket.timeout, OSError, ValueError):
        print(f"Packet {sequence:02d} | TIMEOUT")
    rows.append({"sequence": sequence, "path": PATH, "status": status,
                 "rtt_ms": round(rtt, 4) if rtt is not None else ""})
    time.sleep(INTERVAL)
client.close()
received = len(rtts)
lost = PACKET_COUNT - received
jitter = statistics.mean(abs(rtts[i] - rtts[i-1]) for i in range(1, len(rtts))) if len(rtts) > 1 else 0.0
summary = {"packet_loss_percent": round(lost / PACKET_COUNT * 100, 2),
           "avg_rtt_ms": round(statistics.mean(rtts), 4) if rtts else 0.0,
           "avg_jitter_ms": round(jitter, 4),
           "min_rtt_ms": round(min(rtts), 4) if rtts else 0.0,
           "max_rtt_ms": round(max(rtts), 4) if rtts else 0.0,
           "total_packets_sent": PACKET_COUNT, "total_packets_received": received,
           "total_packets_lost": lost}
try:
    existing = json.loads(JSON_FILE.read_text()) if JSON_FILE.exists() else {}
except (OSError, json.JSONDecodeError):
    existing = {}
paths = existing.get("paths", {})
route = ("H1 -> S1 -> S2 -> S3 -> S4 -> H2" if PATH == "upper"
         else "H1 -> S1 -> S4 -> H2")
paths[PATH] = {"route": route,
               "round_results": [], "summary": summary, "measured": True}
other = "lower" if PATH == "upper" else "upper"
if other not in paths:
    paths[other] = {"route": "Not measured", "round_results": [],
                    "summary": {"packet_loss_percent": 0, "avg_rtt_ms": 0,
                                "avg_jitter_ms": 0, "min_rtt_ms": 0,
                                "max_rtt_ms": 0, "total_packets_sent": 0,
                                "total_packets_received": 0, "total_packets_lost": 0},
                    "measured": False}
measured = [name for name, value in paths.items() if value.get("measured")]
recommended = min(measured, key=lambda name: paths[name]["summary"]["avg_rtt_ms"]) if measured else PATH
JSON_FILE.write_text(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(),
                                 "rounds_per_path": 1, "paths": paths,
                                 "recommended_path": recommended}, indent=2))
with CSV_FILE.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["sequence", "path", "status", "rtt_ms"])
    writer.writeheader(); writer.writerows(rows)
print("\n========== DIAGNOSTIC RESULTS ==========")
print(f"Path             : {PATH.upper()}")
print(f"Packets sent     : {PACKET_COUNT}")
print(f"Packets received : {received}")
print(f"Packets lost     : {lost}")
print(f"Packet loss      : {summary['packet_loss_percent']:.2f}%")
print(f"Average RTT      : {summary['avg_rtt_ms']:.3f} ms")
print(f"Average jitter   : {summary['avg_jitter_ms']:.3f} ms")
print(f"Dashboard JSON   : {JSON_FILE}")
