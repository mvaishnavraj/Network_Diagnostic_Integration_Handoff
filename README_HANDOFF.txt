NETWORK DIAGNOSTIC & PATH ANALYSIS
==================================

This bundle contains two Mininet topologies and the OS-Ken controller, UDP diagnostics, and Flask dashboard. The project Mininet launcher publishes actual `pingall` reachability results to the dashboard. Read PRESENTATION_QUICK_START.md for the demo startup order and UBUNTU_SETUP_AND_TEST_RUNBOOK.md for setup and troubleshooting.

IMPORTANT: Start the OS-Ken controller before Mininet. The Mininet option `--controller=remote,ip=127.0.0.1,port=6653` only points switches at a controller; it does not launch OS-Ken. If the controller is not listening, hosts will show 100% packet loss.

Topology choices
----------------
* `dashboard_sdn/topology.py`, topology name `diamond`: h1, h2, and h3 on a four-switch rhombus.
* `backend_udp/topology_diamond.py`, topology name `diamond3`: the same graph with explicit host IPs.
* `backend_udp/topology_before_failover.py`, topology name `mytopo`: the original h1, h2, and h3 chain topology.
* `backend_udp/topology.py` also defines a three-host diamond under the legacy topology name `mytopo`; `topology_diamond.py` gives that variant explicit host IPs and the clearer name `diamond3`.

The rhombus links are S1-S2, S2-S3, S3-S4, and S1-S4. The upper H1-to-H2 route is H1-S1-S2-S3-S4-H2; the lower route is H1-S1-S4-H2. H3 connects to S2. RTT, jitter, and packet-loss comparisons are for UDP traffic between H1 and H2; H3 is included in the topology but is not measured by those comparisons.

The OS-Ken controller ARP handling uses a discovered spanning tree, avoiding broadcast loops while allowing hosts attached to transit switches (including h3).

Environment
-----------
Use Python 3.10 through 3.13 with OS-Ken 4.2.2. The `.venv` included in the supplied ZIP was made with Python 3.14.4 and an absolute path from another VM; it is not portable. Do not use it. Recreate the virtual environment on the Ubuntu VM using the setup runbook. Mininet and Open vSwitch are system packages; install them with Ubuntu's package manager.

Verification status
-------------------
The changes in this archive have not been run in the user's Ubuntu/Mininet VM. The connectivity failure should be diagnosed with the controller-first startup and matching topology commands in PRESENTATION_QUICK_START.md. If pingall still fails, capture the OS-Ken logs and Mininet output; do not report an unrun test as successful.
