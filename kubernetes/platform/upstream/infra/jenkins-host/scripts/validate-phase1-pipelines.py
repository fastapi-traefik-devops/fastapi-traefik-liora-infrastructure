#!/usr/bin/env python3
"""Validate reviewed pipeline definitions against the local Jenkins controller."""
from __future__ import annotations

import base64
import argparse
import http.cookiejar
import json
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
URL = "http://127.0.0.1:8085"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reload-casc", action="store_true", help="Reload the reviewed local JCasC before validation")
    args = parser.parse_args()
    password = (ROOT / ".jenkins-host/secrets/jenkins-admin-password").read_text().strip()
    authorization = "Basic " + base64.b64encode(("admin:" + password).encode()).decode()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    headers = {"Authorization": authorization}
    request = urllib.request.Request(URL + "/crumbIssuer/api/json", headers=headers)
    with opener.open(request, timeout=60) as response:
        crumb = json.load(response)
    headers[crumb["crumbRequestField"]] = crumb["crumb"]
    if args.reload_casc:
        request = urllib.request.Request(URL + "/configuration-as-code/reload", data=b"", headers=headers)
        with opener.open(request, timeout=120) as response:
            response.read()
        print("PASS: reviewed local JCasC reloaded")
    for name in ("Jenkinsfile", "Jenkinsfile.promote"):
        data = urllib.parse.urlencode({"jenkinsfile": (ROOT / name).read_text()}).encode()
        request = urllib.request.Request(URL + "/pipeline-model-converter/validate", data=data, headers=headers)
        with opener.open(request, timeout=60) as response:
            verdict = response.read().decode()
        if "Jenkinsfile successfully validated" not in verdict:
            raise RuntimeError(f"{name}: {verdict}")
        print(f"PASS: {name} validated by Jenkins")


if __name__ == "__main__":
    main()
