import socket
import json
import time

HOST = "10.0.0.2"
PORT = 5005

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((HOST, PORT))

print(f"UDP Diagnostic Server listening on {HOST}:{PORT}")

while True:
    data, client_address = server.recvfrom(4096)

    try:
        packet = json.loads(data.decode())

        response = {
            "sequence": packet["sequence"],
            "server_receive_time": time.time(),
            "status": "received"
        }

        server.sendto(
            json.dumps(response).encode(),
            client_address
        )

        print(
            f"Received packet {packet['sequence']} "
            f"from {client_address}"
        )

    except (ValueError, KeyError, UnicodeDecodeError) as error:
        print(f"Invalid packet from {client_address}: {error}")
