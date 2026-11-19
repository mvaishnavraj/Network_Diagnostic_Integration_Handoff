
import socket
import json

SERVER_IP = "10.0.0.2"
PORT = 9999

# Create UDP socket
server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind to Host h2
server.bind((SERVER_IP, PORT))

print("================================")
print(" NETWORK DIAGNOSTIC UDP SERVER")
print("================================")
print(f"Listening on {SERVER_IP}:{PORT}")

while True:
    data, client_address = server.recvfrom(2048)

    try:
        packet = json.loads(data.decode())
        sequence = packet["sequence"]

        print(
            f"Received packet #{sequence} "
            f"from {client_address[0]}"
        )

        # Echo the original packet
        server.sendto(data, client_address)

    except (ValueError, KeyError, UnicodeDecodeError):
        print("Invalid packet received")

