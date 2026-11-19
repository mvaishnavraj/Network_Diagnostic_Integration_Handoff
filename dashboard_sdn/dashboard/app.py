
from flask import Flask, render_template_string, jsonify, request
import json
from pathlib import Path
import csv
import socket


app = Flask(__name__)
selected_path = "lower"

RESULTS_FILE = (
    Path(__file__).resolve().parent.parent
    / "results"
    / "latest_comparison.json"
)
PINGALL_FILE = (
    Path(__file__).resolve().parent.parent
    / "results"
    / "latest_pingall.json"
)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Network Diagnostic Dashboard</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    padding: 28px;
    font-family: Arial, sans-serif;
    background: #0b1120;
    color: #e5e7eb;
}

header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 28px;
}

h1 {
    margin: 0;
    color: #60a5fa;
}

.subtitle {
    color: #94a3b8;
    margin-top: 8px;
}

.status {
    background: #422006;
    color: #fbbf24;
    padding: 9px 14px;
    border-radius: 20px;
    font-size: 13px;
}

.section-title {
    font-size: 18px;
    margin: 28px 0 15px;
}

.metrics {
    display: grid;
    grid-template-columns: repeat(4, minmax(160px, 1fr));
    gap: 16px;
}

.card, .panel {
    background: #172338;
    border: 1px solid #26364e;
    border-radius: 12px;
    padding: 20px;
}

.card-label {
    color: #94a3b8;
    font-size: 14px;
}

.metric-value {
    font-size: 29px;
    font-weight: bold;
    margin-top: 13px;
    color: #38bdf8;
}

.metric-note {
    font-size: 12px;
    color: #64748b;
    margin-top: 8px;
}

.main-grid {
    display: grid;
    grid-template-columns: 1.5fr 1fr;
    gap: 18px;
}

/* Network topology (diamond) */
.topology {
    position: relative;
    width: 100%;
    aspect-ratio: 1.65 / 1;
    min-height: 300px;
    margin-top: 10px;
}

.topology svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
}

.wire {
    stroke: #475569;
    stroke-width: 3;
    stroke-linecap: round;
    vector-effect: non-scaling-stroke;
}

.wire.active {
    stroke: #22c55e;
}

.wire.failed {
    stroke: #ef4444;
    stroke-dasharray: 6 6;
}

.topology .node {
    position: absolute;
    transform: translate(-50%, -50%);
    background: #263750;
    border: 2px solid #64748b;
    border-radius: 10px;
    padding: 13px;
    min-width: 58px;
    text-align: center;
    font-weight: bold;
}

.host   { border-color: #38bdf8; }
.switch { border-color: #818cf8; }

/* Rhombus positions (x%, y%) */
.n-h1 { left: 8%;  top: 50%; }
.n-s1 { left: 27%; top: 50%; }
.n-h3 { left: 50%; top: 9%; }
.n-s2 { left: 50%; top: 30%; }
.n-s3 { left: 77%; top: 50%; }
.n-s4 { left: 54%; top: 80%; }
.n-h2 { left: 90%; top: 80%; }

.path-label {
    position: absolute;
    transform: translateX(-50%);
    font-size: 11px;
    color: #94a3b8;
}
.pl-upper { left: 59%; top: 16%; }
.pl-lower { left: 38%; top: 70%; }

button {
    border: 0;
    padding: 11px 16px;
    margin: 8px 6px 0 0;
    border-radius: 7px;
    background: #2563eb;
    color: white;
    cursor: pointer;
    font-weight: bold;
}
button:hover { background: #1d4ed8; }
button.secondary { background: #334155; }

.path-info {
    color: #94a3b8;
    font-size: 13px;
    margin-top: 14px;
}

.activity {
    display: flex;
    flex-direction: column;
    gap: 14px;
}
.event {
    border-left: 3px solid #38bdf8;
    padding: 4px 0 4px 12px;
    font-size: 13px;
    color: #cbd5e1;
}
.event small { display: block; color: #64748b; margin-top: 5px; }

.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td {
    text-align: left;
    padding: 13px;
    border-bottom: 1px solid #29384e;
}
th { color: #94a3b8; font-weight: normal; }

.notice {
    color: #fbbf24;
    font-size: 12px;
    margin-top: 12px;
}

@media (max-width: 900px) {
    .metrics { grid-template-columns: repeat(2, 1fr); }
    .main-grid { grid-template-columns: 1fr; }
}
@media (max-width: 520px) {
    body { padding: 16px; }
    .metrics { grid-template-columns: 1fr 1fr; }
}
</style>
</head>

<body>

<header>
    <div>
        <h1>Network Diagnostic Dashboard</h1>
        <div class="subtitle">Diamond Topology | 3 Hosts / 4 Switches | Network Path Analysis</div>
    </div>
    <div class="status" id="connectionStatus">● CHECKING CONTROLLER</div>
</header>

<h2 class="section-title">Network Performance</h2>

<div class="metrics">
    <div class="card">
        <div class="card-label">Network Status</div>
        <div class="metric-value" id="networkState" style="color:#fbbf24">Checking</div>
        <div class="metric-note" id="networkNote">Checking controller at 127.0.0.1:9999</div>
    </div>
    <div class="card">
        <div class="card-label">Active Path</div>
        <div class="metric-value" id="activePath">Lower</div>
        <div class="metric-note">Controller-selected H1 ↔ H2 route</div>
    </div>
    <div class="card">
        <div class="card-label">Average Latency</div>
        <div class="metric-value" id="latency">-- ms</div>
        <div class="metric-note" id="jitter">H1 ↔ H2 jitter: -- ms</div>
    </div>
    <div class="card">
        <div class="card-label">Packet Loss</div>
        <div class="metric-value" id="packetLoss">-- %</div>
        <div class="metric-note">H1 ↔ H2 UDP test</div>
    </div>
</div>

<h2 class="section-title">Live Reachability — Mininet pingall</h2>
<div class="metrics">
    <div class="card">
        <div class="card-label">ICMP Reachability</div>
        <div class="metric-value" id="pingallStatus" style="color:#fbbf24">Waiting</div>
        <div class="metric-note" id="pingallUpdated">Run pingall in the Mininet terminal</div>
    </div>
    <div class="card">
        <div class="card-label">Hosts Checked</div>
        <div class="metric-value" id="pingallHosts">--</div>
        <div class="metric-note" id="pingallHostNames">Waiting for a Mininet result</div>
    </div>
    <div class="card">
        <div class="card-label">Successful Host Checks</div>
        <div class="metric-value" id="pingallChecks">-- / --</div>
        <div class="metric-note">All ordered host pairs</div>
    </div>
    <div class="card">
        <div class="card-label">ICMP Packet Loss</div>
        <div class="metric-value" id="pingallLoss">-- %</div>
        <div class="metric-note">Reported by the live Mininet pingall</div>
    </div>
</div>

<h2 class="section-title">Network Topology</h2>

<div class="main-grid">
    <div class="panel">
        <div class="card-label">DIAMOND (RHOMBUS) NETWORK — 3 HOSTS / 4 SWITCHES</div>

        <div class="topology">
            <!-- links: coordinates match the node positions in the CSS (in %) -->
            <svg viewBox="0 0 100 100" preserveAspectRatio="none">
                <line class="wire" x1="8" y1="50" x2="27" y2="50"></line>
                <line class="wire" x1="50" y1="9" x2="50" y2="30"></line>
                <line class="wire" id="upper1" x1="27" y1="50" x2="50" y2="30"></line>
                <line class="wire" id="upper2" x1="50" y1="30" x2="77" y2="50"></line>
                <line class="wire" id="upper3" x1="77" y1="50" x2="54" y2="80"></line>
                <line class="wire" id="lower1" x1="27" y1="50" x2="54" y2="80"></line>
                <line class="wire" x1="54" y1="80" x2="90" y2="80"></line>
            </svg>

            <span class="path-label pl-upper">UPPER PATH</span>
            <span class="path-label pl-lower">LOWER PATH</span>

            <div class="node host   n-h1">H1</div>
            <div class="node switch n-s1">S1</div>
            <div class="node host   n-h3">H3</div>
            <div class="node switch n-s2">S2</div>
            <div class="node switch n-s3">S3</div>
            <div class="node switch n-s4">S4</div>
            <div class="node host   n-h2">H2</div>
        </div>

        <div class="path-info">
            H1: 10.0.0.1 (S1) &nbsp; | &nbsp; H2: 10.0.0.2 (S4) &nbsp; | &nbsp; H3: 10.0.0.3 (S2)
            <br>
            Upper path: H1 → S1 → S2 → S3 → S4 → H2
            <br>
            Lower path: H1 → S1 → S4 → H2
        </div>
    </div>

    <div class="panel">
        <div class="card-label">PATH CONTROL</div>
        <h3>Choose Network Route</h3>

        <button onclick="selectPath('upper')">Select Upper Path</button>
        <button onclick="selectPath('lower')">Select Lower Path</button>
        <button class="secondary" onclick="simulateFailure()">Demo Link Failure</button>

        <p id="pathMessage" class="path-info">
            Lower path selected in the dashboard state. Connect the controller to verify it.
        </p>

        <div class="notice">
            Path selection sends a command to the controller. Failure simulation remains a demo.
        </div>
    </div>
</div>

<h2 class="section-title">Failure Recovery Activity</h2>
<div class="panel activity" id="activity">
    <div class="event">
        Dashboard initialized
        <small>Waiting for Ubuntu network connection</small>
    </div>
</div>

<h2 class="section-title">Failure Recovery Results</h2>

<div class="metrics">
    <div class="card">
        <div class="card-label">Packets Sent</div>
        <div class="metric-value" id="failureSent">--</div>
    </div>

    <div class="card">
        <div class="card-label">Packets Received</div>
        <div class="metric-value" id="failureReceived">--</div>
    </div>

    <div class="card">
        <div class="card-label">Packets Lost</div>
        <div class="metric-value" id="failureLost">--</div>
    </div>

    <div class="card">
        <div class="card-label">Failure Test Loss</div>
        <div class="metric-value" id="failureLoss">-- %</div>
    </div>
</div>

<h2 class="section-title">Path Comparison — H1 ↔ H2</h2>
<div class="panel table-wrap">
    <table>
        <thead>
            <tr>
                <th>Metric</th>
                <th>Upper Path</th>
                <th>Lower Path</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Average RTT</td>
                <td id="upperRtt">--</td>
                <td id="lowerRtt">--</td>
            </tr>
            <tr>
                <td>Average Jitter</td>
                <td id="upperJitter">--</td>
                <td id="lowerJitter">--</td>
            </tr>
            <tr>
                <td>Packet Loss</td>
                <td id="upperLoss">--</td>
                <td id="lowerLoss">--</td>
            </tr>
            <tr>
                <td>Recommendation</td>
                <td colspan="2" id="recommendation">Awaiting diagnostic tests</td>
            </tr>
        </tbody>
    </table>
    <div class="notice">RTT, jitter, and packet loss here are measured between H1 and H2. H3 is shown in the topology but is not included in these measurements.</div>
</div>

<script>
let currentPath = "lower";
let failedPath = null;
let lastPingallTimestamp = null;

function updateTopology() {
    const routeLinks = {
        upper: ["upper1", "upper2", "upper3"],
        lower: ["lower1"]
    };

    ["upper", "lower"].forEach(p => {
        const isActive = currentPath === p && failedPath !== p;
        const isFailed = failedPath === p;
        routeLinks[p].forEach(id => {
            const el = document.getElementById(id);
            el.classList.toggle("active", isActive);
            el.classList.toggle("failed", isFailed);
        });
    });

    document.getElementById("activePath").textContent =
        currentPath.charAt(0).toUpperCase() + currentPath.slice(1);
}

function simulateFailure() {
    if (failedPath) return;   // a failure is already being shown

    failedPath = currentPath;
    updateTopology();

    document.getElementById("pathMessage").textContent =
        "Demo: " + failedPath.toUpperCase() + " path link failed. Rerouting...";
    addActivity("Demo link failure on " + failedPath.toUpperCase() + " path");

    setTimeout(() => {
        currentPath = failedPath === "upper" ? "lower" : "upper";
        updateTopology();

        document.getElementById("pathMessage").textContent =
            "Demo: traffic rerouted to " + currentPath.toUpperCase() + " path.";
        addActivity("Demo recovery: rerouted to " + currentPath.toUpperCase() + " path");
    }, 1500);
}

function addActivity(message) {
    const activity = document.getElementById("activity");
    const item = document.createElement("div");
    item.className = "event";
    item.textContent = message;

    const time = document.createElement("small");
    time.textContent = new Date().toLocaleTimeString();
    item.appendChild(time);

    activity.prepend(item);
}

async function selectPath(path) {
    try {
        const response = await fetch("/api/path", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ path: path })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Path selection failed");
        }

        currentPath = data.active_path;
        failedPath = null;
        updateTopology();

        document.getElementById("pathMessage").textContent =
            "Backend confirmed: " + currentPath.toUpperCase() + " path selected.";

        addActivity("Backend path selection: " + currentPath.toUpperCase());

    } catch (error) {
        document.getElementById("pathMessage").textContent =
            "Error: " + error.message;
    }
}

async function loadDiagnosticResults() {
    try {
        const response = await fetch("/api/results");

        if (!response.ok) {
            throw new Error("Could not load diagnostic results");
        }

        const data = await response.json();

        const path = data.recommended_path;
        const summary = data.paths[path].summary;
        const upper = data.paths.upper.summary;
        const lower = data.paths.lower.summary;

        // Upper path measurements
        document.getElementById("upperRtt").textContent =
            upper.avg_rtt_ms.toFixed(4) + " ms";
        document.getElementById("upperJitter").textContent =
            upper.avg_jitter_ms.toFixed(4) + " ms";
        document.getElementById("upperLoss").textContent =
            upper.packet_loss_percent + " %";

        // Lower path measurements
        document.getElementById("lowerRtt").textContent =
            lower.avg_rtt_ms.toFixed(4) + " ms";
        document.getElementById("lowerJitter").textContent =
            lower.avg_jitter_ms.toFixed(4) + " ms";
        document.getElementById("lowerLoss").textContent =
            lower.packet_loss_percent + " %";

        // Recommended path
        document.getElementById("recommendation").textContent =
            path.toUpperCase() + " PATH";

        document.getElementById("latency").textContent =
            summary.avg_rtt_ms.toFixed(4) + " ms";

        document.getElementById("jitter").textContent =
            "H1 ↔ H2 jitter: " + summary.avg_jitter_ms.toFixed(4) + " ms";

        document.getElementById("packetLoss").textContent =
            summary.packet_loss_percent + " %";

        addActivity("Diagnostic results loaded successfully.");
    } catch (error) {
        console.error(error);
        addActivity("Could not load diagnostic results.");
    }
}

async function loadPingallResults() {
    try {
        const response = await fetch("/api/pingall", { cache: "no-store" });
        const data = await response.json();

        if (!data.available) {
            document.getElementById("pingallStatus").textContent = "Waiting";
            document.getElementById("pingallUpdated").textContent =
                "Run pingall in the Mininet terminal";
            return;
        }

        const state = document.getElementById("pingallStatus");
        const labels = { pass: "All reachable", partial: "Partial loss", failed: "Unreachable" };
        state.textContent = labels[data.status] || "Result available";
        state.style.color = data.status === "pass" ? "#22c55e" : "#fbbf24";
        document.getElementById("pingallHosts").textContent = data.host_count;
        document.getElementById("pingallHostNames").textContent =
            (data.hosts || []).join(", ");
        document.getElementById("pingallChecks").textContent =
            data.checks_received + " / " + data.checks_total;
        document.getElementById("pingallLoss").textContent =
            Number(data.packet_loss_percent).toFixed(2) + " %";

        const timestamp = data.timestamp_utc
            ? new Date(data.timestamp_utc).toLocaleString()
            : "Timestamp unavailable";
        document.getElementById("pingallUpdated").textContent =
            "Last run: " + timestamp;

        if (data.timestamp_utc && data.timestamp_utc !== lastPingallTimestamp) {
            lastPingallTimestamp = data.timestamp_utc;
            addActivity("Live Mininet pingall: " + data.checks_received + "/" +
                data.checks_total + " checks passed, " +
                Number(data.packet_loss_percent).toFixed(2) + "% loss.");
        }
    } catch (error) {
        document.getElementById("pingallStatus").textContent = "Unavailable";
        document.getElementById("pingallUpdated").textContent =
            "Could not load the Mininet pingall report";
    }
}

async function loadFailureResults() {
    try {
        const response = await fetch("/api/failure");

        if (!response.ok) {
            throw new Error("Could not load failure results");
        }

        const data = await response.json();

        document.getElementById("failureSent").textContent =
            data.total_packets;

        document.getElementById("failureReceived").textContent =
            data.received;

        document.getElementById("failureLost").textContent =
            data.lost;

        document.getElementById("failureLoss").textContent =
            data.packet_loss_percent + " %";

        addActivity("Failure recovery results loaded.");

    } catch (error) {
        console.error(error);
    }
}

async function loadStatus() {
    try {
        const response = await fetch("/api/status");
        const data = await response.json();
        const online = data.network === "connected";
        document.getElementById("connectionStatus").textContent = online ? "● CONTROLLER CONNECTED" : "● CONTROLLER OFFLINE";
        document.getElementById("networkState").textContent = online ? "Online" : "Offline";
        document.getElementById("networkState").style.color = online ? "#22c55e" : "#fbbf24";
        document.getElementById("networkNote").textContent = online ? "OS-Ken path-control listener responding" : "Start the OS-Ken controller";
        if (online && data.active_path) { currentPath = data.active_path; updateTopology(); }
    } catch (error) {
        document.getElementById("connectionStatus").textContent = "● API UNAVAILABLE";
        document.getElementById("networkState").textContent = "Offline";
    }
}

loadStatus();
loadFailureResults();
loadDiagnosticResults();
loadPingallResults();
setInterval(() => {
    loadStatus();
    loadDiagnosticResults();
    loadFailureResults();
    loadPingallResults();
}, 5000);

updateTopology();
</script>

</body>
</html>
"""

@app.route("/")
def dashboard():
    return render_template_string(HTML)


@app.route("/api/status")
def status():
    global selected_path
    network = "offline"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.settimeout(0.5)
            probe.sendto(selected_path.encode("ascii"), ("127.0.0.1", 9999))
            reply, _ = probe.recvfrom(1024)
        message = reply.decode("utf-8", errors="replace")
        if message.startswith("Active path:"):
            network = "connected"
            selected_path = message.split(":", 1)[1].strip().lower()
    except (OSError, socket.timeout):
        pass
    return jsonify({"mode": "live" if network == "connected" else "offline",
                    "network": network, "active_path": selected_path})


@app.route("/api/pingall")
def get_pingall_results():
    if not PINGALL_FILE.exists():
        return jsonify({"available": False, "message": "Run pingall in Mininet"})

    try:
        with PINGALL_FILE.open("r", encoding="utf-8") as report_file:
            report = json.load(report_file)
        if not isinstance(report, dict):
            raise ValueError("Pingall report must contain a JSON object")
        report["available"] = True
        return jsonify(report)
    except (json.JSONDecodeError, OSError, ValueError) as error:
        return jsonify({"available": False, "error": str(error)}), 500


@app.route("/api/path", methods=["POST"])
def change_path():
    global selected_path

    data = request.get_json(silent=True) or {}
    path = data.get("path", "").lower()

    if path not in ("upper", "lower"):
        return jsonify({"error": "Invalid path"}), 400

    # The controller listens on this local UDP socket (see controller/test_controller.py).
    # Do not report success unless it confirms the requested route.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as control_socket:
            control_socket.settimeout(2.0)
            control_socket.sendto(path.encode("ascii"), ("127.0.0.1", 9999))
            response, _ = control_socket.recvfrom(1024)
        message = response.decode("utf-8", errors="replace")
    except (OSError, socket.timeout) as error:
        return jsonify({"error": f"Controller unavailable: {error}"}), 503

    expected = f"Active path: {path}"
    if message != expected:
        return jsonify({"error": message or "Controller rejected path selection"}), 502

    selected_path = path

    return jsonify({
        "success": True,
        "active_path": selected_path
    })

@app.route("/api/results")
def get_results():
    if not RESULTS_FILE.exists():
        return jsonify({"error": "No diagnostic results found"}), 404

    try:
        with open(RESULTS_FILE, "r") as file:
            results = json.load(file)

        return jsonify(results)

    except (json.JSONDecodeError, OSError) as error:
        return jsonify({"error": str(error)}), 500
    
FAILURE_FILE = (
    Path(__file__).resolve().parent.parent
    / "results"
    / "latest_failure_recovery.csv"
)


@app.route("/api/failure")
def get_failure_results():
    if not FAILURE_FILE.exists():
        return jsonify({"error": "No failure report found"}), 404

    try:
        with open(FAILURE_FILE, "r", newline="") as file:
            rows = list(csv.DictReader(file))

        total = len(rows)
        received = sum(
            row["status"] == "received" for row in rows
        )
        lost = total - received

        return jsonify({
            "total_packets": total,
            "received": received,
            "lost": lost,
            "packet_loss_percent": round(
                lost / total * 100, 2
            ) if total else 0,
            "events": rows
        })

    except (OSError, KeyError) as error:
        return jsonify({"error": str(error)}), 500
    
if __name__ == "__main__":
    app.run(debug=True)
