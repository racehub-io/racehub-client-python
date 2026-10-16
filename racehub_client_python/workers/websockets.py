import json
import sys


def send_message(action, payload):
    """
    Send a message to the server through stdout
    """

    message = json.dumps({"action": action, "payload": payload})
    sys.stdout.write(f"{message}\n")
    sys.stdout.flush()
