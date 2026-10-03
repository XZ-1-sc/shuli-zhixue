"""Recover an Aiven MySQL service that the free tier powered off.

Used by the scheduled GitHub Actions workflow. Only a confirmed powered-off
service is changed; every other state is left alone.
"""

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def request(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"aivenv1 {token}",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req, timeout=25) as response:
        return json.load(response)


def check_and_recover(project: str, service_name: str, token: str) -> str:
    url = (
        "https://api.aiven.io/v1/project/"
        f"{quote(project, safe='')}/service/{quote(service_name, safe='')}"
    )
    service = request("GET", url, token)["service"]
    state = str(service.get("state", "")).upper()
    powered = service.get("powered")
    plan = str(service.get("plan", ""))

    # Fail closed if the API response differs from the expected shape.
    if service.get("service_type") != "mysql":
        raise RuntimeError("Configured Aiven service is not MySQL")
    if plan and not plan.startswith("free"):
        raise RuntimeError("Configured Aiven service is not on a Free plan")

    if powered is False or state in {"POWEROFF", "POWER_OFF"}:
        request("PUT", url, token, {"powered": True})
        return "Power-on requested"
    if powered is True or state in {"RUNNING", "REBALANCING", "REBUILDING"}:
        return f"No action needed ({state or 'powered'})"
    raise RuntimeError(f"Unexpected Aiven service state: {state or 'missing'}")


def main() -> int:
    project = os.environ.get("AIVEN_PROJECT", "").strip()
    service_name = os.environ.get("AIVEN_SERVICE", "").strip()
    token = os.environ.get("AIVEN_API_TOKEN", "").strip()
    if not all((project, service_name, token)):
        print("Missing AIVEN_PROJECT, AIVEN_SERVICE, or AIVEN_API_TOKEN", file=sys.stderr)
        return 1
    try:
        print(check_and_recover(project, service_name, token))
        return 0
    except (HTTPError, URLError, KeyError, RuntimeError, ValueError) as exc:
        # Do not print response bodies: they can include connection details.
        print(f"Aiven recovery failed: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
