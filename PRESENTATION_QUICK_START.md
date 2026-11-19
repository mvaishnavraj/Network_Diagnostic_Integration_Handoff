# Presentation quick start (Ubuntu VM)

Run this project inside Ubuntu, where Mininet and Open vSwitch are installed. The Mininet `--controller=remote` option only configures the switches to connect to a controller; it does **not** start OS-Ken. Start OS-Ken first in its own terminal.

Use Python 3.10–3.13 for OS-Ken 4.2.2. The `.venv` included in the uploaded ZIP was created on Python 3.14.4 at a different absolute path, so it is not portable. Recreate it using the setup guide before running this sequence.

## 1. Start OS-Ken — Terminal 1

```bash
cd ~/Documents/Network_Diagnostic_Integration_Handoff
source .venv/bin/activate
cd dashboard_sdn
python -m controller.launcher controller.test_controller os_ken.topology.switches
```

Keep this terminal open. Wait for `Path control listener active on 127.0.0.1:9999`. In Terminal 2, confirm the OpenFlow port is listening before starting Mininet:

```bash
ss -ltnp | grep ':6653'
ss -lunp | grep ':9999'
```

If TCP port 6653 is not listening, do not start Mininet. The controller command failed or the OS-Ken environment is not usable. Read the error in Terminal 1.

## 2. Start the three-host diamond — Terminal 2

Use the project launcher below. It starts the three-host diamond and gives you the usual `mininet>` prompt. Its `pingall` command also saves the actual ICMP reachability result for the dashboard. Run it with the system Python because Mininet is installed by Ubuntu, not in the OS-Ken virtual environment:

```bash
cd ~/Documents/Network_Diagnostic_Integration_Handoff
sudo /usr/bin/python3 dashboard_sdn/mininet_dashboard.py
```

At `mininet>`, check that the network and controller are ready:

```text
nodes
net
links
```

Confirm the output lists `h1`, `h2`, `h3`, `s1`, `s2`, `s3`, and `s4`. In Terminal 1, wait until the controller logs the four switch connections and discovered inter-switch links. Then run:

```text
pingall
```

The dashboard's **Live Reachability — Mininet pingall** section updates from that run. It shows host count, successful directed host checks, ICMP packet loss, and run time. Expected result is 0% dropped. If it still reports loss, check Terminal 1 for OpenFlow errors and confirm TCP 6653 was listening before Mininet started. Do not try `link`, `link all`, or `link h3` to discover hosts; use `nodes` and `net`. The `link` command needs two node names and an optional `up`/`down`, for example `link s1 s2 down`.

For topology-only troubleshooting, `sudo mn --custom dashboard_sdn/topology.py --topo diamond --controller=remote,ip=127.0.0.1,port=6653 --switch ovs,protocols=OpenFlow13` still works, but its plain `pingall` output is not written to the dashboard.

The controller's ARP forwarding uses a spanning tree of discovered links. This avoids ARP loops in the diamond and supports h3 on s2. Once all four switches and their links appear in the controller log, run `pingall`; expected result is 0% dropped.

## 3. Topology and measurement notes

The UDP path comparison measures traffic between h1 and h2. H3 is present on s2 for connectivity demonstrations but is not included in the RTT, jitter, or loss comparison. `backend_udp/topology_diamond.py --topo diamond3` defines the same three-host graph with explicit IP addresses if you prefer the backend folder's topology file.

## 4. Measure UDP on the diamond

At `mininet>` start the echo server on h2:

```text
h2 python3 -u /home/vboxuser/Documents/Network_Diagnostic_Integration_Handoff/dashboard_sdn/diagnostics/udp_server.py > /tmp/udp-server.log 2>&1 &
```

If `$PROJECT` is not set in Mininet's shell, use the full path to the project folder, such as `/home/vboxuser/Documents/Network_Diagnostic_Integration_Handoff/dashboard_sdn/diagnostics/udp_server.py`.

Run each path measurement once:

```text
h1 python3 -u /home/vboxuser/Documents/Network_Diagnostic_Integration_Handoff/dashboard_sdn/diagnostics/udp_client.py upper
h1 python3 -u /home/vboxuser/Documents/Network_Diagnostic_Integration_Handoff/dashboard_sdn/diagnostics/udp_client.py lower
```

Replace `/home/vboxuser/Documents/Network_Diagnostic_Integration_Handoff` if your Ubuntu username or project location differs. The client writes measurements under `dashboard_sdn/results/` for the dashboard.

## 5. Dashboard and live path selection — Terminal 3

```bash
cd ~/Documents/Network_Diagnostic_Integration_Handoff
source .venv/bin/activate
cd dashboard_sdn/dashboard
python app.py
```

Open `http://127.0.0.1:5000` inside Ubuntu. The path buttons require the OS-Ken controller. Dashboard measurements populate after both upper and lower UDP runs.

## 6. Real link-failure test (only after normal UDP succeeds)

At `mininet>`, start the continuous probe and take down a link on the selected path. For the default lower route:

```text
h1 python3 -u /home/vboxuser/Documents/Network_Diagnostic_Integration_Handoff/dashboard_sdn/diagnostics/failure_probe.py > /tmp/failure-probe.log 2>&1 &
link s1 s4 down
```

Watch Terminal 1 for link removal and rerouting messages. Restore the link after observing recovery:

```text
link s1 s4 up
```

The probe runs for up to 90 seconds. The dashboard's “Demo Link Failure” button is still visual only; use Mininet's `link ... down/up` command for a real failure.

If the VM lags or freezes, stop and capture both terminal logs. Do not repeatedly relaunch Mininet. This runbook is not a claim that the Ubuntu tests have already passed.
