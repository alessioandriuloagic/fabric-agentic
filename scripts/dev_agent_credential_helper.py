"""Private localhost credential helper used by the Dev Agent dispatcher."""

import json
import os
import socket
import subprocess
import sys


def request_token(kind: str) -> str:
    endpoint = os.environ["FABRIC_AGENT_CREDENTIAL_BROKER"]
    host, port = endpoint.split(":", 1)
    with socket.create_connection((host, int(port)), timeout=5) as connection:
        connection.sendall((json.dumps({"kind": kind}) + "\n").encode("utf-8"))
        response = json.loads(connection.recv(4096).decode("utf-8"))
    if response.get("error"):
        raise RuntimeError("credential broker rejected request")
    return response["token"]


def main() -> int:
    mode = sys.argv[1]
    if mode == "git":
        print("x-access-token")
        print(request_token("git"))
        return 0
    if mode == "gh":
        real_gh = sys.argv[2]
        environment = os.environ.copy()
        environment["GH_TOKEN"] = request_token("gh")
        result = subprocess.run([real_gh, *sys.argv[3:]], env=environment, check=False)
        return result.returncode
    return 1


if __name__ == "__main__":
    raise SystemExit(main())