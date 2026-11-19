# Network Diagnostic & Path Analysis Tool

A Mininet and SDN project that compares alternate network routes, measures UDP performance, checks host reachability, and presents results in a Flask dashboard.

## Project overview

The demo network has three hosts and four Open vSwitch switches. H1 and H2 are the endpoints used for UDP path measurements; H3 is attached to S2 and is included in reachability checks.

```text
                    H3
                    |
                    S2 ---- S3
                   /          \
H1 ---- S1 -------------------- S4 ---- H2
       \_____ lower route _____/
```

- **Upper path:** H1 → S1 → S2 → S3 → S4 → H2
- **Lower path:** H1 → S1 → S4 → H2

## Architecture

1. **Mininet and Open vSwitch** create the hosts, switches, and links.
2. **OS-Ken** communicates with the switches using OpenFlow 1.3, learns the switch topology, and installs forwarding rules for the selected path. It listens for OpenFlow connections on TCP port `6653`.
3. **UDP diagnostics** send numbered packets from H1 to an echo server on H2. The client calculates round-trip time (RTT), jitter, and packet loss.
4. **The Flask dashboard** reads the saved JSON and CSV results and displays reachability, selected path, performance, and recovery activity.

The dashboard sends route-selection commands to the controller over UDP on `127.0.0.1:9999`. The integrated diagnostic echo server listens on H2 at UDP port `5005`. These are separate connections.

## Main files

| File or folder | Purpose |
|---|---|
| `dashboard_sdn/topology.py` | Three-host, four-switch diamond topology used by the integrated demo. |
| `dashboard_sdn/mininet_dashboard.py` | Starts Mininet and saves actual `pingall` reachability results for the dashboard. |
| `dashboard_sdn/controller/launcher.py` | Starts the requested OS-Ken apps and topology discovery. |
| `dashboard_sdn/controller/test_controller.py` | Active controller: tracks links, accepts upper/lower path choices, installs flows, and attempts rerouting after a link change. |
| `dashboard_sdn/diagnostics/udp_server.py` | UDP echo server to run on H2. |
| `dashboard_sdn/diagnostics/udp_client.py` | Sends 50 probes and saves RTT, jitter, and loss measurements. |
| `dashboard_sdn/diagnostics/failure_probe.py` | Sends probes during a failure demonstration and writes a CSV timeline. |
| `dashboard_sdn/dashboard/app.py` | Flask application serving the dashboard and its result endpoints. |
| `dashboard_sdn/results/` | Dashboard result files, including latest pingall, UDP comparison, and failure-probe data. |
| `backend_udp/` | Earlier standalone UDP, discovery, and topology prototypes. Use the integrated scripts under `dashboard_sdn/` for the dashboard demo. |

## Requirements

Run the project in an Ubuntu VM with Mininet and Open vSwitch installed. Use Python **3.10–3.13** for OS-Ken 4.2.2. Mininet is installed as an Ubuntu system package; OS-Ken and Flask run in a virtual environment.

Install system packages if they are not already installed:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-dev build-essential mininet openvswitch-switch iproute2
sudo systemctl enable --now openvswitch-switch
```

From the project root, create the virtual environment with a supported Python version:

```bash
cd /path/to/Network_Diagnostic_Integration_Handoff
PYTHON_BIN="$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3.10)"
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install os-ken==4.2.2 Flask networkx
.venv/bin/python -m pip check
```

Do not use a virtual environment copied from another computer or VM; virtual environments contain machine-specific paths.

## Run the demo

Use three Ubuntu terminals and keep the controller and Mininet terminals open while testing. Set `PROJECT` to the absolute project path separately in each terminal; shell variables do not automatically carry between terminals.

```bash
PROJECT="$HOME/path/to/Network_Diagnostic_Integration_Handoff"
```

### Terminal 1: start OS-Ken

```bash
PROJECT="$HOME/path/to/Network_Diagnostic_Integration_Handoff"
cd "$PROJECT/dashboard_sdn"
"$PROJECT/.venv/bin/python" -m controller.launcher controller.test_controller os_ken.topology.switches
```

Wait for the controller to start and listen on `127.0.0.1:9999` before starting Mininet. The Mininet remote-controller setting points to OS-Ken; it does not start OS-Ken itself.

### Terminal 2: start Mininet

```bash
PROJECT="$HOME/path/to/Network_Diagnostic_Integration_Handoff"
cd "$PROJECT"
sudo /usr/bin/python3 dashboard_sdn/mininet_dashboard.py
```

At the `mininet>` prompt, check the network:

```text
nodes
net
links
pingall
```

With three hosts, `pingall` checks six directed host-to-host pairs. Its output is ICMP reachability, not the UDP RTT test.

### Terminal 3: start the dashboard

```bash
PROJECT="$HOME/path/to/Network_Diagnostic_Integration_Handoff"
cd "$PROJECT/dashboard_sdn/dashboard"
"$PROJECT/.venv/bin/python" app.py
```

Open `http://127.0.0.1:5000` in a browser inside Ubuntu.

### Run UDP measurements

At the Mininet prompt, start the echo server on H2. Replace `/path/to/Network_Diagnostic_Integration_Handoff` with the actual absolute project path; Mininet hosts need the full path to the script.

```text
h2 python3 -u /path/to/Network_Diagnostic_Integration_Handoff/dashboard_sdn/diagnostics/udp_server.py > /tmp/udp-server.log 2>&1 &
```

Use the dashboard to select a route, then run the corresponding client from H1:

```text
h1 python3 -u /path/to/Network_Diagnostic_Integration_Handoff/dashboard_sdn/diagnostics/udp_client.py upper
h1 python3 -u /path/to/Network_Diagnostic_Integration_Handoff/dashboard_sdn/diagnostics/udp_client.py lower
```

The client sends 50 packets per run and writes results under `dashboard_sdn/results/`. Run both paths to compare their measurements. The path argument labels the result; select that route in the dashboard/controller before running the client so the label matches the active route.

## Link failure demonstration

First confirm normal UDP communication works. Then start the continuous probe on H1 and take down a link on the active route. For example, when the lower route is active:

```text
h1 python3 -u /path/to/Network_Diagnostic_Integration_Handoff/dashboard_sdn/diagnostics/failure_probe.py > /tmp/failure-probe.log 2>&1 &
link s1 s4 down
```

Watch the controller log for link-change and rerouting messages. Restore the link afterward:

```text
link s1 s4 up
```

The failure probe runs for up to 90 seconds. The dashboard's **Demo Link Failure** button is a visual demonstration; use Mininet's `link ... down/up` commands to create a real link failure.

## Troubleshooting

- **All hosts fail `pingall`:** check that OS-Ken is still running and that TCP port `6653` was listening before Mininet started. Check the controller terminal for switch connection and OpenFlow errors.
- **A topology command says a file cannot be found:** run it from the project root and use the matching file path under `dashboard_sdn/`.
- **A UDP probe times out:** confirm the UDP server is running on H2 and listening on port `5005`; check the selected path and host IPs.
- **Mininet reports an interface already exists:** stop the existing Mininet session first. Only use `sudo mn -c` after confirming no other Mininet lab is active, because it cleans Mininet runtime state.
- **The VM becomes unresponsive:** stop repeated topology launches and inspect the VM/kernel logs before trying again.

## Results and verification

The dashboard shows the latest files saved under `dashboard_sdn/results/`. Results can change from run to run, and old files may remain until a new run replaces them. A dashboard value is a measurement only when it came from a completed diagnostic run; this README does not claim that the commands have been executed on every user's VM.

## GitHub

Keep `.venv/`, credentials, access tokens, and private data out of the repository. For this project, the virtual environment should be recreated on the Ubuntu VM rather than committed to GitHub.
