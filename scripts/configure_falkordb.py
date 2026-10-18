"""Update local FalkorDB settings without displaying or overwriting other secrets."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


def main() -> int:
    if not ENV_FILE.exists():
        print("Backend .env not found. Copy .env.example to .env first.")
        return 1

    print("Enter the values from your FalkorDB Cloud Connectivity / User Access pages.")
    print("Input is stored only in the ignored local .env file; password input is hidden.")
    host = input("Host (hostname only, no port): ").strip()
    if "://" in host or "/" in host:
        print("Enter only the host name, without scheme, path, or port.")
        return 1
    port = input("Port [51603]: ").strip() or "51603"
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        print("Port must be a number between 1 and 65535.")
        return 1
    username = input("Username: ").strip()
    password = getpass("Password (hidden): ")
    if not host or not username or not password:
        print("Host, username, and password are required.")
        return 1

    updates = {
        "FALKORDB_HOST": host,
        "FALKORDB_PORT": port,
        "FALKORDB_USERNAME": username,
        "FALKORDB_PASSWORD": password,
        "FALKORDB_GRAPH": "nexushelper",
        "FALKORDB_USE_TLS": "true",
    }
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    found: set[str] = set()
    output: list[str] = []
    for line in lines:
        key, separator, _ = line.partition("=")
        if separator and key in updates:
            output.append(f"{key}={updates[key]}")
            found.add(key)
        else:
            output.append(line)
    for key, value in updates.items():
        if key not in found:
            output.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(output) + "\n", encoding="utf-8")
    ENV_FILE.chmod(0o600)
    print("Updated local FalkorDB settings. Values were not displayed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
