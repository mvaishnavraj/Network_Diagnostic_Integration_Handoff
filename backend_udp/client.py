
import socket
import time
import json
import csv
from datetime import datetime, timezone

# Configuration
SERVER_IP = "10.0.0.2"
PORT = 9999
TOTAL_PACKETS = 20
TIMEOUT = 1.0
INTERVAL = 0.2

# Create UDP socket
client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server_address = (SERVER_IP, PORT)

received_packets = 0
rtt_values = []
packet_records = []

print("================================")
print(" NETWORK DIAGNOSTIC CLIENT")
print("================================")
print(f"Destination: {SERVER_IP}:{PORT}")
print(f"Packets to send: {TOTAL_PACKETS}")
print()

for sequence in range(1, TOTAL_PACKETS + 1):

    # Record sending timestamp
    sent_utc = datetime.now(timezone.utc).isoformat()
    sent_ns = time.perf_counter_ns()

    # Create structured diagnostic packet
    packet = {
        "sequence": sequence,
        "sent_at": sent_utc
    }

    message = json.dumps(packet).encode()

    try:
        client.sendto(message, server_address)

        # Wait for the matching response
        deadline = time.monotonic() + TIMEOUT
        matched = False

        while time.monotonic() < deadline:

            remaining = deadline - time.monotonic()
            client.settimeout(remaining)

            try:
                data, address = client.recvfrom(2048)

                response = json.loads(data.decode())

                # Verify sequence number
                if response.get("sequence") != sequence:
                    print("Unexpected packet received")
                    continue

                # Calculate RTT
                received_ns = time.perf_counter_ns()

                rtt = (received_ns - sent_ns) / 1_000_000

                received_packets += 1
                rtt_values.append(rtt)
                matched = True

                print(
                    f"Packet {sequence}: RECEIVED | "
                    f"RTT: {rtt:.3f} ms"
                )

                packet_records.append({
                    "sequence": sequence,
                    "sent_at_utc": sent_utc,
                    "destination": SERVER_IP,
                    "status": "RECEIVED",
                    "rtt_ms": round(rtt, 3)
                })

                break

            except socket.timeout:
                break

            except (ValueError, UnicodeDecodeError):
                print("Invalid response received")

        if not matched:
            print(f"Packet {sequence}: LOST / TIMEOUT")

            packet_records.append({
                "sequence": sequence,
                "sent_at_utc": sent_utc,
                "destination": SERVER_IP,
                "status": "LOST",
                "rtt_ms": ""
            })

    except OSError as error:
        print(f"Packet {sequence}: Socket error: {error}")

        packet_records.append({
            "sequence": sequence,
            "sent_at_utc": sent_utc,
            "destination": SERVER_IP,
            "status": "ERROR",
            "rtt_ms": ""
        })

    time.sleep(INTERVAL)

client.close()

# Calculate statistics
sent_packets = sum(
    1 for record in packet_records
    if record["status"] in ("RECEIVED", "LOST")
)

lost_packets = sum(
    1 for record in packet_records
    if record["status"] == "LOST"
)

packet_loss = (
    (lost_packets / sent_packets) * 100
    if sent_packets else 0
)

average_rtt = (
    sum(rtt_values) / len(rtt_values)
    if rtt_values else 0
)

minimum_rtt = min(rtt_values) if rtt_values else 0
maximum_rtt = max(rtt_values) if rtt_values else 0

# Save individual packet results
with open("packet_results.csv", "w", newline="") as file:

    fields = [
        "sequence",
        "sent_at_utc",
        "destination",
        "status",
        "rtt_ms"
    ]

    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()
    writer.writerows(packet_records)

# Save summary
with open("diagnostic_summary.csv", "w", newline="") as file:

    fields = [
        "packets_sent",
        "packets_received",
        "packets_lost",
        "packet_loss_percent",
        "average_rtt_ms",
        "minimum_rtt_ms",
        "maximum_rtt_ms"
    ]

    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()

    writer.writerow({
        "packets_sent": TOTAL_PACKETS,
        "packets_received": received_packets,
        "packets_lost": lost_packets,
        "packet_loss_percent": round(packet_loss, 2),
        "average_rtt_ms": round(average_rtt, 3),
        "minimum_rtt_ms": round(minimum_rtt, 3),
        "maximum_rtt_ms": round(maximum_rtt, 3)
    })

# Display final report
print("\n================================")
print("       DIAGNOSTIC REPORT")
print("================================")

print(f"Packets sent:     {TOTAL_PACKETS}")
print(f"Packets received: {received_packets}")
print(f"Packets lost:     {lost_packets}")
print(f"Packet loss:      {packet_loss:.2f}%")

print(f"Average RTT:      {average_rtt:.3f} ms")
print(f"Minimum RTT:      {minimum_rtt:.3f} ms")
print(f"Maximum RTT:      {maximum_rtt:.3f} ms")

print("\nCSV reports saved:")
print("1. packet_results.csv")
print("2. diagnostic_summary.csv")

