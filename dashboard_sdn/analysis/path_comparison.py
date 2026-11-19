import csv
import json
import re
import socket
import time
from pathlib import Path
from datetime import datetime
from statistics import mean

PROJECT = Path(__file__).resolve().parent.parent
CLIENT = PROJECT / "diagnostics" / "udp_client.py"
RESULTS = PROJECT / "results"

ROUNDS = 5

PATHS = {
    "upper": "H1 -> S1 -> S2 -> S3 -> S4 -> H2",
    "lower": "H1 -> S1 -> S4 -> H2"
}


def select_path(path):
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(3)

    try:
        client.sendto(path.encode(), ("127.0.0.1", 9999))
        response, _ = client.recvfrom(1024)

        message = response.decode()

        if f"Active path: {path}" not in message:
            raise RuntimeError(message)

        print(f"\nSelected path: {path.upper()}")
        print(message)

    finally:
        client.close()


def run_diagnostic():
    output = net.get("h1").cmd(
        f"python3 -u {CLIENT}"
    )

    patterns = {
        "packets_sent": r"Packets sent\s*:\s*(\d+)",
        "packets_received": r"Packets received\s*:\s*(\d+)",
        "packets_lost": r"Packets lost\s*:\s*(\d+)",
        "packet_loss_percent": r"Packet loss\s*:\s*([\d.]+)",
        "min_rtt_ms": r"Minimum RTT\s*:\s*([\d.]+)",
        "max_rtt_ms": r"Maximum RTT\s*:\s*([\d.]+)",
        "avg_rtt_ms": r"Average RTT\s*:\s*([\d.]+)",
        "avg_jitter_ms": r"Average jitter\s*:\s*([\d.]+)"
    }

    result = {}

    for key, pattern in patterns.items():
        match = re.search(pattern, output)

        if match:
            value = match.group(1)

            if key in (
                "packets_sent",
                "packets_received",
                "packets_lost"
            ):
                result[key] = int(value)
            else:
                result[key] = float(value)
        else:
            result[key] = None

    if result["packets_sent"] is None:
        raise RuntimeError(
            "Could not parse diagnostic output:\n" + output
        )

    if result["packets_received"] == 0:
        raise RuntimeError(
            "No UDP packets received. Check the UDP server."
        )

    return result


def summarize_rounds(rounds):
    metrics = [
        "packet_loss_percent",
        "avg_rtt_ms",
        "avg_jitter_ms",
        "min_rtt_ms",
        "max_rtt_ms"
    ]

    summary = {}

    for metric in metrics:
        values = [
            item[metric]
            for item in rounds
            if item[metric] is not None
        ]

        summary[metric] = round(mean(values), 4)

    summary["total_packets_sent"] = sum(
        item["packets_sent"] for item in rounds
    )

    summary["total_packets_received"] = sum(
        item["packets_received"] for item in rounds
    )

    summary["total_packets_lost"] = sum(
        item["packets_lost"] for item in rounds
    )

    return summary


def main():
    RESULTS.mkdir(exist_ok=True)

    server_status = net.get("h2").cmd(
        "ss -ulnp | grep 5005"
    )

    if "5005" not in server_status:
        raise RuntimeError(
            "UDP server is not running on H2 port 5005."
        )

    report = {
        "timestamp": datetime.now().isoformat(),
        "rounds_per_path": ROUNDS,
        "paths": {}
    }

    for path, description in PATHS.items():

        print("\n" + "=" * 60)
        print(f"PERFORMANCE TEST: {path.upper()} PATH")
        print(description)
        print("=" * 60)

        round_results = []

        for round_number in range(1, ROUNDS + 1):

            print(
                f"\nRound {round_number}/{ROUNDS}"
            )

            select_path(path)
            time.sleep(0.5)

            metrics = run_diagnostic()
            metrics["round"] = round_number

            round_results.append(metrics)

            print(
                f"Received: {metrics['packets_received']}/"
                f"{metrics['packets_sent']} | "
                f"Loss: {metrics['packet_loss_percent']}% | "
                f"Average RTT: {metrics['avg_rtt_ms']} ms | "
                f"Jitter: {metrics['avg_jitter_ms']} ms"
            )

        report["paths"][path] = {
            "route": description,
            "round_results": round_results,
            "summary": summarize_rounds(round_results)
        }

    # Rank by packet loss, then average RTT, then jitter.
    def ranking(path):
        summary = report["paths"][path]["summary"]

        return (
            summary["packet_loss_percent"],
            summary["avg_rtt_ms"],
            summary["avg_jitter_ms"]
        )

    recommended = min(
        ("upper", "lower"),
        key=ranking
    )

    report["recommended_path"] = recommended

    print("\n" + "=" * 60)
    print("FINAL PERFORMANCE COMPARISON")
    print("=" * 60)

    print(
        f"{'Metric':<25}"
        f"{'Upper':<17}"
        f"{'Lower':<17}"
    )

    comparison_metrics = [
        ("Average RTT (ms)", "avg_rtt_ms"),
        ("Average jitter (ms)", "avg_jitter_ms"),
        ("Packet loss (%)", "packet_loss_percent")
    ]

    for label, key in comparison_metrics:

        upper = report["paths"]["upper"]["summary"][key]
        lower = report["paths"]["lower"]["summary"][key]

        print(
            f"{label:<25}"
            f"{upper:<17}"
            f"{lower:<17}"
        )

    print("\nRECOMMENDED PATH:", recommended.upper())
    print(PATHS[recommended])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_file = RESULTS / f"comparison_{timestamp}.json"
    csv_file = RESULTS / f"comparison_{timestamp}.csv"

    latest_json = RESULTS / "latest_comparison.json"
    latest_csv = RESULTS / "latest_comparison.csv"

    json_data = json.dumps(report, indent=4)

    json_file.write_text(json_data)
    latest_json.write_text(json_data)

    csv_columns = [
        "path",
        "round",
        "packets_sent",
        "packets_received",
        "packets_lost",
        "packet_loss_percent",
        "min_rtt_ms",
        "max_rtt_ms",
        "avg_rtt_ms",
        "avg_jitter_ms"
    ]

    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=csv_columns
        )

        writer.writeheader()

        for path, path_data in report["paths"].items():
            for result in path_data["round_results"]:

                row = {
                    "path": path,
                    **result
                }

                writer.writerow(row)

    latest_csv.write_text(csv_file.read_text())

    print("\nREPORTS SAVED:")
    print(json_file)
    print(csv_file)
    print(latest_json)
    print(latest_csv)


if __name__ == "__main__":
    main()
