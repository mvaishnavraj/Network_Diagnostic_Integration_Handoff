
import subprocess

def run_command(command):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip().strip('"')

print("\n======================================")
print("       LIVE NETWORK DIAGNOSTICS")
print("======================================")

# Discover switches
bridges = run_command(
    ["ovs-vsctl", "list-br"]
).splitlines()

print("\n1. ACTIVE SWITCHES")

for bridge in bridges:
    print("Switch:", bridge)

print("\nTotal switches:", len(bridges))

# Discover ports and their states
print("\n2. INTERFACE STATUS REPORT")

total_ports = 0
up_ports = 0
down_ports = 0

for bridge in bridges:

    ports = run_command(
        ["ovs-vsctl", "list-ports", bridge]
    ).splitlines()

    print(f"\nSwitch: {bridge}")

    for port in ports:

        admin = run_command(
            ["ovs-vsctl", "get", "Interface",
             port, "admin_state"]
        )

        link = run_command(
            ["ovs-vsctl", "get", "Interface",
             port, "link_state"]
        )

        ofport = run_command(
            ["ovs-vsctl", "get", "Interface",
             port, "ofport"]
        )

        total_ports += 1

        if admin == "up" and link == "up":
            status = "UP"
            up_ports += 1
        else:
            status = "DOWN"
            down_ports += 1

        print(f"  Interface: {port}")
        print(f"  OpenFlow port: {ofport}")
        print(f"  Admin state: {admin}")
        print(f"  Link state: {link}")
        print(f"  Status: {status}")
        print("  ------------------------")

# Final report
loss_percentage = (
    down_ports / total_ports * 100
    if total_ports else 0
)

print("\n======================================")
print("       DIAGNOSTIC SUMMARY")
print("======================================")

print("Active switches:", len(bridges))
print("Total ports:", total_ports)
print("Ports UP:", up_ports)
print("Ports DOWN:", down_ports)
print(f"Port down percentage: {loss_percentage:.2f}%")

print("\nLive diagnostics completed!")
