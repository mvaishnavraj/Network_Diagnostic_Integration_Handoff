
from topology import MyTopo

# Load the existing Mininet topology
topo = MyTopo()

# Discover hosts and switches
hosts = topo.hosts()
switches = topo.switches()

# Discover all links
links = topo.links()

print("\n===================================")
print("       NETWORK DISCOVERY")
print("===================================")

print("\n1. DISCOVERED HOSTS")
for host in hosts:
    print(f"   Host: {host}")

print(f"\nTotal hosts: {len(hosts)}")

print("\n2. DISCOVERED SWITCHES")
for switch in switches:
    print(f"   Switch: {switch}")

print(f"\nTotal switches: {len(switches)}")

print("\n3. DISCOVERED LINKS")
for source, destination in links:
    print(f"   {source} <----> {destination}")

print(f"\nTotal links: {len(links)}")

print("\n===================================")
print("       DISCOVERY SUMMARY")
print("===================================")
print(f"Hosts discovered:   {len(hosts)}")
print(f"Switches discovered: {len(switches)}")
print(f"Links discovered:   {len(links)}")
print("Discovery completed successfully.")
