#!/usr/bin/env python3
"""Run the project diamond with a Mininet CLI that publishes pingall results."""

import json
import os
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

from mininet.cli import CLI
from mininet.log import output, setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController

from topology import DiamondTopo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PINGALL_FILE = PROJECT_ROOT / "dashboard_sdn" / "results" / "latest_pingall.json"


class DashboardCLI(CLI):
    """Keep Mininet's pingall command and also save its live summary."""

    def do_pingall(self, line):
        """Ping every ordered host pair and publish the measured loss."""
        timeout = line.strip() or None
        loss_percent = self.mn.pingAll(timeout=timeout)

        hosts = [host.name for host in self.mn.hosts]
        checks_total = len(hosts) * max(0, len(hosts) - 1)
        loss_percent = float(loss_percent or 0.0)
        checks_lost = min(
            checks_total,
            max(0, round(checks_total * loss_percent / 100.0)),
        )
        checks_received = checks_total - checks_lost

        if checks_total == 0:
            result = "unavailable"
        elif checks_lost == 0:
            result = "pass"
        elif checks_received > 0:
            result = "partial"
        else:
            result = "failed"

        report = {
            "available": True,
            "source": "Mininet pingall",
            "protocol": "ICMP",
            "topology": "diamond",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "hosts": hosts,
            "host_count": len(hosts),
            "checks_total": checks_total,
            "checks_received": checks_received,
            "checks_lost": checks_lost,
            "packet_loss_percent": round(loss_percent, 2),
            "status": result,
        }

        try:
            PINGALL_FILE.parent.mkdir(parents=True, exist_ok=True)
            temporary_file = PINGALL_FILE.with_suffix(".json.tmp")
            temporary_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            temporary_file.chmod(0o644)
            os.replace(temporary_file, PINGALL_FILE)
            output("Dashboard updated with this pingall result.\n")
        except OSError as error:
            output("Could not save pingall result for dashboard: %s\n" % error)


def main():
    setLogLevel("info")
    network = Mininet(
        topo=DiamondTopo(),
        controller=None,
        switch=partial(OVSSwitch, protocols="OpenFlow13"),
        autoSetMacs=True,
    )
    network.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6653,
    )

    try:
        output("*** Starting the project diamond with the OS-Ken controller\n")
        network.start()
        if not network.waitConnected(timeout=15):
            output("*** Warning: not all switches connected; check the controller terminal\n")
        DashboardCLI(network)
    except KeyboardInterrupt:
        output("\n*** Stopping the project diamond\n")
    finally:
        network.stop()


if __name__ == "__main__":
    main()
