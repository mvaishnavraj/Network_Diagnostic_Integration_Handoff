import socket
import sys

if len(sys.argv) != 2 or sys.argv[1].lower() not in ("upper", "lower"):
    print("Usage: python tools/select_path.py [upper|lower]")
    sys.exit(1)

command = sys.argv[1].lower()

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.settimeout(3)

try:
    client.sendto(command.encode(), ("127.0.0.1", 9999))
    response, _ = client.recvfrom(1024)
    print(response.decode())
except socket.timeout:
    print("ERROR: Controller did not respond.")
    sys.exit(1)
finally:
    client.close()
