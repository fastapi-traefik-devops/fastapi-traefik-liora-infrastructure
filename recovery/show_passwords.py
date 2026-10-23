#!/usr/bin/env python3
"""Print current browser credentials after explicit interactive confirmation."""

import argparse
import base64
import binascii
import json
from pathlib import Path
import subprocess
import sys

import yaml


class ReadError(Exception):
    """A safe diagnostic containing resource identifiers only."""


def read_data(config, namespace, kind, name):
    location = f"{namespace}/{kind}/{name}"
    try:
        result = subprocess.run(
            ["kubectl", f"--kubeconfig={config}", "--request-timeout=30s",
             "-n", namespace, "get", kind, name, "-o", "json"],
            capture_output=True, text=True, timeout=45, check=False,
        )
        if result.returncode:
            raise ReadError(f"Cannot read {location}; check kubeconfig and RBAC.")
        data = json.loads(result.stdout)["data"]
        if not isinstance(data, dict):
            raise ValueError
        return data
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError):
        raise ReadError(f"Cannot read {location}; check kubectl and cluster access.") from None


def field(data, key, encoded=False):
    try:
        value = data[key]
        if encoded:
            value = base64.b64decode(value, validate=True).decode("utf-8")
        if not isinstance(value, str) or not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError
        return value
    except (KeyError, ValueError, TypeError, binascii.Error):
        raise ReadError(f"Missing or invalid field {key}; cannot render a safe TSV table.") from None


def collect(configs, backup=None):
    sections = []
    for cluster, environments, vip in [
        ("prod", ["prod"], "192.168.77.17"),
        ("nonprod", ["stage", "dev"], "192.168.77.16"),
    ]:
        def read(namespace, kind, name):
            return read_data(configs[cluster], namespace, kind, name)

        argo = read("argocd", "secret", "argocd-initial-admin-secret")
        grafana = read("monitoring", "secret", "monitoring-grafana-admin")
        shared = [
            ("Argo CD", f"https://{vip}:8080", "admin", field(argo, "password", True)),
            ("Grafana", f"http://{vip}:3000", field(grafana, "admin-user", True),
             field(grafana, "admin-password", True)),
            ("Prometheus", f"http://{vip}:9090", "—", "—"),
            ("Alertmanager", f"http://{vip}:9093", "—", "—"),
        ]
        for env in environments:
            namespace = f"app-{env}"
            backend_config = read(namespace, "configmap", "backend-config")
            backend = read(namespace, "secret", "backend-secrets")
            if backend_config.get("POSTGRES_USER") == "app_owner":
                db = read(namespace, "secret", "cnpg-superuser")
                db_login, db_password = field(db, "username", True), field(db, "password", True)
            else:
                db_config = read(namespace, "configmap", "db-config")
                db = read(namespace, "secret", "db-secrets")
                db_login, db_password = field(db_config, "POSTGRES_USER"), field(db, "POSTGRES_PASSWORD", True)
            hostname = "liora.aprt.info" if env == "prod" else f"{env}.liora.aprt.info"
            port = 8082 if env == "stage" else 8081
            rows = [("Application", f"https://{hostname}/", field(backend_config, "FIRST_SUPERUSER"),
                     field(backend, "FIRST_SUPERUSER_PASSWORD", True))]
            rows.extend(shared)
            rows.append(("Adminer", f"http://{vip}:{port}", db_login, db_password))
            sections.append((env.upper(), rows))
    jenkins = read_data(configs["nonprod"], "jenkins", "secret", "jenkins-foundation-login")
    sections.append(("NONPROD (shared DEV/STAGE)", [
        ("Jenkins", "http://192.168.77.16:8085", "admin",
         field(jenkins, "jenkins-admin-password", True)),
    ]))
    if backup:
        rows = [('R2 S3', field(backup, 'endpoint') + '/' + field(backup, 'bucket'),
                 field(backup, 'access_key_id'), field(backup, 'secret_access_key'))]
        if backup.get('api_token'):
            rows.append(('R2 API token', 'https://dash.cloudflare.com/', field(backup, 'account_id'),
                         field(backup, 'api_token')))
        sections.append(('DATABASE BACKUPS (shared bucket credential)', rows))
    return sections


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nonprod-kubeconfig", default=str(Path.home() / ".kube/config-dev-stage"))
    parser.add_argument("--prod-kubeconfig", default=str(Path.home() / ".kube/config-prod"))
    args = parser.parse_args()
    print("WARNING: all passwords will now be printed in plaintext. "
          "Redirected stdout will send them to a file or pipe. Continue? y/n: ",
          end="", file=sys.stderr, flush=True)
    try:
        answer = sys.stdin.readline().strip().lower()
    except OSError:
        print("Cannot read confirmation from stdin; no credentials read.", file=sys.stderr)
        return 2
    if answer != "y":
        print("Cancelled; no credentials read.", file=sys.stderr)
        return 0
    try:
        # Collect everything first: a failed read must not emit a partial password table.
        recovery = Path(__file__).resolve().parent / "recovery.yaml"
        backup = yaml.safe_load(recovery.read_text()).get("database_backups") if recovery.exists() else None
        sections = collect({"nonprod": args.nonprod_kubeconfig, "prod": args.prod_kubeconfig}, backup)
    except (OSError, yaml.YAMLError) as error:
        print("ERROR: Cannot read private recovery YAML; no credentials printed.", file=sys.stderr)
        return 1
    except ReadError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    lines = ["PASSWORDS:"]
    for title, rows in sections:
        lines.extend(["", f"{title}:", "SERVICE\tURL\tLOGIN\tPASS"])
        lines.extend("\t".join(row) for row in rows)
    lines.extend(["", "Adminer: PostgreSQL; server=db; database=app.",
                  "DEV/STAGE share Argo CD, Grafana and Jenkins. — = no separate authentication.",
                  "Argo CD: initial Secret password; may be stale after manual rotation.",
                  "Stored credentials only; application/database login validity is not checked."])
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)
