# Ubuntu setup and staged test runbook

This guide is for the existing project folder on an Ubuntu Mininet VM. It separates read-only checks, system package installation, and tests that start Mininet. Do not run the topology until the VM checks pass.

## 1. Check the VM before changing it

Run these in an Ubuntu terminal and save the output:

```bash
date -Is
lsb_release -a
uname -a
nproc
free -h
df -h /
python3 --version
command -v mn || true
mn --version 2>&1 || true
command -v ovs-vsctl || true
ovs-vsctl --version 2>&1 | head -n 2 || true
systemctl is-active openvswitch-switch 2>&1 || true
```

Use Python 3.10–3.13 for OS-Ken 4.2.2. Mininet and the custom topology run in the system Python environment; OS-Ken and Flask will be isolated in a project virtual environment. Do not use `sudo pip`. The `.venv` included in the supplied ZIP was created with Python 3.14.4 at a different absolute path; do not use it.

If the VM has frozen before, inspect the current and prior boot kernel logs before restarting the topology:

```bash
sudo journalctl -k -b --no-pager | tail -n 150
sudo journalctl -k -b -1 --no-pager | tail -n 150
```

Look for `Out of memory`, `oom-kill`, `Killed process`, kernel panic, OVS errors, or repeated interface/namespace creation. The prior-boot command may have no output if the VM does not retain journal logs.

## 2. Install system dependencies (Ubuntu)

These commands change the VM and require administrator privileges. Review the VM checks first. On Ubuntu, install the distro Mininet/OVS packages and Python tooling:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-dev build-essential mininet openvswitch-switch iproute2 net-tools curl
sudo systemctl enable --now openvswitch-switch
```

Confirm the installed tools and versions:

```bash
python3 --version
mn --version
ovs-vsctl --version | head -n 2
systemctl is-active openvswitch-switch
```

Check for a supported interpreter:

```bash
command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3.10
```

If none is available, stop and use an Ubuntu release with Python 3.10–3.13 (for example Ubuntu 24.04 with Python 3.12). Do not replace Ubuntu's system Python or try to run OS-Ken 4.2.2 with Python 3.14 for this demo.

## 3. Locate the project and create an isolated Python environment

Set `PROJECT` to the directory containing `README_HANDOFF.txt`, `backend_udp/`, and `dashboard_sdn/`. For example, if copied to the home directory:

```bash
export PROJECT="$HOME/Network_Diagnostic_Integration_Handoff"
test -f "$PROJECT/README_HANDOFF.txt" && test -d "$PROJECT/dashboard_sdn" && echo "Project path OK"
```

Create a virtual environment inside the project and install the Python app dependencies:

```bash
PYTHON_BIN="$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3.10)"
if [ -d "$PROJECT/.venv" ]; then mv "$PROJECT/.venv" "$PROJECT/.venv-python314-backup-$(date +%Y%m%d%H%M%S)"; fi
"$PYTHON_BIN" -m venv "$PROJECT/.venv"
"$PROJECT/.venv/bin/python" -m pip install --upgrade pip
"$PROJECT/.venv/bin/python" -m pip install os-ken==4.2.2 Flask networkx
"$PROJECT/.venv/bin/python" -m pip check
"$PROJECT/.venv/bin/python" -c 'import flask, networkx, os_ken; print("Flask", flask.__version__); print("NetworkX", networkx.__version__); print("OS-Ken", os_ken.__file__)'
```

The Python client/server scripts otherwise use only the standard library. Mininet and Open vSwitch are system packages, not dependencies to install into this virtual environment.

## 4. Safe Mininet baseline, then controller

First check whether another Mininet lab is active:

```bash
pgrep -af 'mn|ovs-vswitchd|ovsdb-server' || true
sudo ovs-vsctl show
```

Do not run `sudo mn -c` if another lab is active; it removes Mininet runtime state. If this VM is dedicated to this project and there is no other Mininet lab, clean stale Mininet state before the first attempt:

```bash
sudo mn -c
```

Start the controller in **Terminal 1** (ordinary user, no `sudo`):

```bash
cd "$PROJECT/dashboard_sdn"
"$PROJECT/.venv/bin/python" -m controller.launcher controller.test_controller os_ken.topology.switches
```

Wait for the log line indicating the path-control listener is on `127.0.0.1:9999`. Keep this terminal open. In a second Ubuntu terminal, confirm the controller port is listening before starting Mininet:

```bash
ss -ltnp | grep ':6653' || true
ss -lunp | grep ':9999' || true
```

OS-Ken's OpenFlow listener is expected on TCP port 6653; the project's path-selection listener is UDP port 9999.

## 5. Start the diamond topology (only after the checks above)

Start the topology in **Terminal 2** with the project launcher. It provides the standard Mininet prompt and saves each `pingall` result where the dashboard can read it. Use Ubuntu's system Python here because Mininet is installed as an OS package:

```bash
cd "$PROJECT"
sudo /usr/bin/python3 dashboard_sdn/mininet_dashboard.py
```

Do not run multiple Mininet topologies at once. The original direct Mininet command remains available for topology-only troubleshooting, but it does not publish `pingall` results to the dashboard:

```bash
cd "$PROJECT"
sudo mn --custom dashboard_sdn/topology.py --topo diamond --controller=remote,ip=127.0.0.1,port=6653 --switch ovs,protocols=OpenFlow13
```

The controller must still be running in Terminal 1 for either topology. `backend_udp/topology_before_failover.py --topo mytopo` remains the original chain topology if you need it.

At the `mininet>` prompt, begin with low-impact checks:

```text
nodes
net
links
```

Verify the controller log reports all four switches connected and LLDP-discovered links. Then check that the hosts have the expected addresses:

```text
h1 ip -br address
h2 ip -br address
h3 ip -br address
```

The project launcher uses `dashboard_sdn/topology.py` to create the three-host rhombus: H1-S1-S2-S3-S4-H2 is the upper path, and H1-S1-S4-H2 is the lower path; H3 connects to S2. Use the controller's spanning-tree ARP forwarding to avoid loops while reaching this intermediate host. Wait until the controller reports all four switches and discovered links before `pingall`. The launcher saves each result to `dashboard_sdn/results/latest_pingall.json`; the dashboard reads it through `/api/pingall`.

If `pingall` reports 100% dropped, first check that the OS-Ken process is still running and TCP port 6653 was listening before Mininet started. The remote-controller option only points Mininet at OS-Ken; it does not start OS-Ken. Check Terminal 1 for switch connection logs and OpenFlow errors. Do not repeatedly relaunch Mininet if the VM becomes unresponsive.

Exit Mininet with `exit`. Only use `sudo mn -c` after confirming no other Mininet lab is active.

## 6. UDP diagnostics (after topology startup is stable)

Start the dashboard diagnostic echo server from the Mininet CLI:

```text
h2 python3 -u /home/vboxuser/Documents/Network_Diagnostic_Integration_Handoff/dashboard_sdn/diagnostics/udp_server.py > /tmp/network-diagnostic-udp-server.log 2>&1 &
h2 ss -ulnp
```

Run the client from h1 once for each path and capture its actual output:

```text
h1 python3 -u /home/vboxuser/Documents/Network_Diagnostic_Integration_Handoff/dashboard_sdn/diagnostics/udp_client.py upper
h1 python3 -u /home/vboxuser/Documents/Network_Diagnostic_Integration_Handoff/dashboard_sdn/diagnostics/udp_client.py lower
```

Replace the example project path if your Ubuntu username or location differs. The expected server port is UDP 5005. The client sends 50 packets and reports sent/received/lost, packet loss, RTT, and average jitter; it writes the dashboard comparison JSON and per-packet CSV under `dashboard_sdn/results/`.

## 7. Path selection and failover (do not start until ARP handling is loop-free)

The current active path defaults to `lower`. In the Ubuntu host shell, command the controller and confirm its reply:

```bash
"$PROJECT/.venv/bin/python" -c 'import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(3); s.sendto(b"lower",("127.0.0.1",9999)); print(s.recvfrom(1024)[0].decode()); s.close()'
```

For a controlled failover run, start a continuous probe from h1, then use the Mininet CLI to disable the direct link on the active lower route and watch the controller logs for `LINK REMOVED`, `PATH FAILOVER`, and `REROUTING COMPLETE`:

```text
h1 python3 -u "$PROJECT/dashboard_sdn/diagnostics/failure_probe.py" > /tmp/failure-probe.log 2>&1 &
link s1 s4 down
```

After observing the reroute, restore the link:

```text
link s1 s4 up
```

The probe runs for 90 seconds and writes `dashboard_sdn/results/latest_failure_recovery.csv`, which the dashboard reads. Replace `/home/vboxuser/Documents/Network_Diagnostic_Integration_Handoff` in the command if your project path differs.

## 8. Dashboard and remaining integration

Start the dashboard from an Ubuntu host terminal:

```bash
cd "$PROJECT/dashboard_sdn/dashboard"
"$PROJECT/.venv/bin/python" app.py
```

It listens on localhost port 5000. From the Ubuntu VM, check its API without exposing it to the network:

```bash
curl -i http://127.0.0.1:5000/api/status
curl -i http://127.0.0.1:5000/api/results
curl -i -H 'Content-Type: application/json' -d '{"path":"upper"}' http://127.0.0.1:5000/api/path
```

The path API now requests controller confirmation. Metrics integration is still incomplete: `/api/results` reads `dashboard_sdn/results/latest_comparison.json`, but the UDP diagnostic client only prints results, and `analysis/path_comparison.py` references an undefined `net` variable. The dashboard will show actual diagnostic values only after the measurement pipeline writes the expected comparison JSON or the API is changed to read the UDP results directly. Do not treat a successful HTTP response from `/api/status` as proof that measurements are integrated.

## 9. Safest SSH access for assisted setup

Use a VirtualBox **Host-only Adapter** for SSH from the Windows host to the guest. Keep the guest SSH service available only on that host-only interface; do not forward SSH or the dashboard to the public internet. In the VM console, find the host-only IP using `ip -br address`.

On Windows PowerShell, create a dedicated key if you do not already have one:

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\mininet_project_ed25519"
```

Keep the private key (`mininet_project_ed25519`) on your PC. Add only the `.pub` public key to the Ubuntu user's `~/.ssh/authorized_keys`, then connect with:

```powershell
ssh -i "$env:USERPROFILE\.ssh\mininet_project_ed25519" UBUNTU_USER@HOST_ONLY_IP
```

For this session, share only the Ubuntu username, host-only IP, SSH port if not 22, and confirmation that the public key is installed. Do not send a password, private key, or a publicly reachable SSH endpoint. Before I run package-install or Mininet commands over SSH, I will show you the specific privileged command and get your approval.

## Stop and report

If the VM stalls, do not immediately relaunch Mininet. Record the exact last command, whether the guest is responsive to SSH, the controller and Mininet terminal output, `free -h`, and the kernel log lines above. If the guest is frozen, capture the VirtualBox VM log (`Logs/VBox.log`) after safely powering off, then share the relevant tail; redact usernames or host paths if desired.
