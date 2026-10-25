#!/usr/bin/env python3
"""Read-only recovery validation. Diagnostics contain locations, never values."""
import datetime
import base64
import ipaddress
import json
import os
from pathlib import Path
import re
import ssl
import stat
import sys
import warnings
import urllib.error
import urllib.parse
import urllib.request

try:
    import yaml
    from cryptography.exceptions import UnsupportedAlgorithm
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
    from email_validator import validate_email, EmailNotValidError
except ImportError:
    print('ERROR: Install recovery/requirements.txt in the selected Python environment.', file=sys.stderr)
    sys.exit(2)

ENV_REQUIRED = {
    'TF_VAR_pm_endpoint', 'TF_VAR_pm_node', 'TF_VAR_pm_api_token',
    'DISK_STORAGE', 'TF_VAR_cloud_init_datastore_id',
    'TAILSCALE_API_KEY', 'TAILSCALE_TAILNET',
}
GHCR = {'GHCR_REGISTRY', 'GHCR_USERNAME', 'GHCR_TOKEN'}
ENV_SUPPORTED = ENV_REQUIRED | GHCR | {'PROXMOX_PUBLIC_IP'}
OBSOLETE = {'SECRET_KEY', 'FIRST_SUPERUSER', 'FIRST_SUPERUSER_PASSWORD',
            'POSTGRES_PASSWORD', 'SMTP_PASSWORD', 'TAILSCALE_AUTH_KEY'}


class InvalidData(Exception):
    pass


class MarkedDict(dict):
    def __init__(self):
        super().__init__()
        self.locations = {}


class Loader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        result = MarkedDict()
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=True)
            if not isinstance(key, str) or key in result:
                raise InvalidData('mapping keys must be unique strings')
            result[key] = self.construct_object(value_node, deep=True)
            result.locations[key] = key_node.start_mark.line + 1
        return result


Loader.add_constructor('tag:yaml.org,2002:map', Loader.construct_mapping)


def env_value(raw, previous):
    """Small assignment grammar, deliberately not a shell interpreter."""
    result, quote, i = [], None, 0
    raw = raw.lstrip()
    while i < len(raw):
        char = raw[i]
        if char == "'" and quote != '"':
            quote = None if quote == "'" else "'"
        elif char == '"' and quote != "'":
            quote = None if quote == '"' else '"'
        elif quote != "'" and char == '\\':
            i += 1
            if i >= len(raw):
                raise InvalidData()
            if quote == '"' and raw[i] not in '$`"\\':
                result.append('\\')
            result.append(raw[i])
        elif quote != "'" and char == '$':
            match = re.match(r'\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))', raw[i:])
            if not match:
                raise InvalidData()
            name = match[1] or match[2]
            if name not in previous:
                raise InvalidData()
            result.append(previous[name])
            i += len(match[0]) - 1
        elif quote is None and char.isspace():
            tail = raw[i:].lstrip()
            if tail and not tail.startswith('#'):
                raise InvalidData()
            break
        elif quote is None and i == 0 and char == '#':
            break
        elif (quote != "'" and char == '`') or (quote is None and char in ';|&<>()'):
            raise InvalidData()
        else:
            result.append(char)
        i += 1
    if quote:
        raise InvalidData()
    return ''.join(result)


class Check:
    def __init__(self, directory, all_fields=True):
        self.directory, self.all_fields = Path(directory), all_fields
        self.errors = self.warnings = 0

    def error(self, location, message):
        self.errors += 1
        print(f'ERROR: {location}: {message}', file=sys.stderr)

    def warn(self, location, message):
        self.warnings += 1
        print(f'WARN: {location}: {message}', file=sys.stderr)

    def read(self, name, private=True, required=True):
        path = self.directory / name
        label = 'recovery/' + name
        try:
            if not path.exists() and not required:
                return None
            if private and stat.S_IMODE(path.stat().st_mode) & 0o077:
                self.error(label, 'must not be accessible to group or others (use chmod 600)')
            value = path.read_bytes()
            if not value:
                self.error(label, 'file is empty')
                return None
            return value
        except OSError:
            self.error(label, 'file is missing or unreadable')
            return None

    def text(self, value, location, empty=False):
        if not isinstance(value, str) or '\0' in value or (not empty and not value):
            self.error(location, 'must be a string without NUL' + ('' if empty else ' and must not be empty'))
            return False
        try:
            value.encode('utf-8')
        except UnicodeError:
            self.error(location, 'must be valid UTF-8 text')
            return False
        if value and (value.upper().startswith(('REPLACE_WITH_', 'CHANGE_ME', 'FAKE_')) or
                      value == 'changethis'):
            self.error(location, 'replace the example/default value')
            return False
        return True

    def env(self):
        raw = self.read('.env')
        values, locations = {}, {}
        if raw is None:
            return values
        try:
            lines = raw.decode('utf-8').splitlines()
        except UnicodeError:
            self.error('recovery/.env', 'must be UTF-8')
            return values
        for number, line in enumerate(lines, 1):
            location = f'recovery/.env:{number}'
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            match = re.fullmatch(r'\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)', line)
            if not match:
                self.error(location, 'expected a single variable assignment; shell commands are unsupported')
                continue
            name = match[1]
            location += ' ' + name
            if name not in ENV_SUPPORTED:
                self.warn(location, 'obsolete variable; move application credentials to YAML or use ephemeral auth inputs'
                          if name in OBSOLETE else 'unknown variable; review manually')
            if name in locations:
                self.error(location, 'duplicate variable assignment')
                continue
            locations[name] = number
            try:
                values[name] = env_value(match[2], values)
            except InvalidData:
                self.error(location, 'invalid assignment; use literal quotes or references to earlier variables')
        required = ENV_REQUIRED | (GHCR if self.all_fields else set())
        for name in sorted(required - values.keys()):
            self.error('recovery/.env ' + name, 'required variable is missing')
        for name, value in values.items():
            if name not in ENV_SUPPORTED:
                continue
            location = f'recovery/.env:{locations[name]} {name}'
            if not self.text(value, location):
                continue
            valid = True
            if name == 'TF_VAR_pm_endpoint':
                try:
                    url = urllib.parse.urlsplit(value)
                    host = url.hostname
                    valid = (url.scheme == 'https' and bool(host) and url.username is None and url.password is None
                             and not url.netloc.endswith(':')
                             and url.path in ('', '/') and '?' not in value and '#' not in value
                             and not re.search(r'[\s\\\x00-\x1f\x7f]', value)
                             and (url.port is None or 1 <= url.port <= 65535))
                    if host:
                        try:
                            ipaddress.ip_address(host)
                        except ValueError:
                            valid = valid and len(host) <= 253 and all(
                                re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', p)
                                for p in host.rstrip('.').split('.'))
                except ValueError:
                    valid = False
            elif name == 'TF_VAR_pm_node':
                valid = bool(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?', value))
            elif name == 'TF_VAR_pm_api_token':
                match = re.fullmatch(r'([^\s:/]+@[A-Za-z][A-Za-z0-9._-]+)!([A-Za-z][A-Za-z0-9._-]+)=([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})', value)
                valid = bool(match and 3 <= len(match[1]) <= 64)
            elif name in {'DISK_STORAGE', 'TF_VAR_cloud_init_datastore_id'}:
                valid = bool(re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*[A-Za-z0-9]', value))
            elif name == 'TAILSCALE_API_KEY':
                valid = bool(re.fullmatch(r'tskey-api-[A-Za-z0-9_-]+', value))
            elif name == 'TAILSCALE_TAILNET':
                valid = bool(re.fullmatch(r'[A-Za-z0-9_.@-]+', value))
            elif name == 'GHCR_REGISTRY':
                valid = value == 'ghcr.io'
            elif name == 'GHCR_USERNAME':
                valid = (len(value) <= 39 and '--' not in value and
                         bool(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?', value)))
            elif name == 'GHCR_TOKEN':
                valid = bool(re.fullmatch(r'(?:ghp_[A-Za-z0-9]{36}|[0-9a-fA-F]{40})', value))
            elif name == 'PROXMOX_PUBLIC_IP':
                try:
                    ipaddress.IPv4Address(value)
                except ValueError:
                    valid = False
            if not valid:
                self.error(location, 'invalid format or length; see recovery/README.md')
        if ('DISK_STORAGE' in values and 'TF_VAR_cloud_init_datastore_id' in values and
                values['DISK_STORAGE'] != values['TF_VAR_cloud_init_datastore_id']):
            self.error('recovery/.env TF_VAR_cloud_init_datastore_id', 'must equal DISK_STORAGE')
        return values

    def mapping(self, value, path, allowed, required=None):
        if not isinstance(value, dict):
            self.error(path, 'must be a mapping')
            return {}
        for key in value:
            location = path + '.' + json.dumps(key, ensure_ascii=True)
            if isinstance(value, MarkedDict):
                location += f' (recovery/recovery.yaml:{value.locations[key]})'
            if key not in allowed:
                self.warn(location, 'unknown or obsolete key; review manually')
                self.unknown_keys(value[key], path + '.' + json.dumps(key, ensure_ascii=True))
        for key in sorted((allowed if required is None else required) - value.keys()):
            self.error(path + '.' + key, 'required key is missing')
        return value

    def unknown_keys(self, value, path):
        """Report names inside unsupported sections too, without their scalar values."""
        if isinstance(value, dict):
            for key, child in value.items():
                location = path + '.' + json.dumps(key, ensure_ascii=True)
                if isinstance(value, MarkedDict):
                    location += f' (recovery/recovery.yaml:{value.locations[key]})'
                self.warn(location, 'unknown or obsolete key; review manually')
                self.unknown_keys(child, path + '.' + json.dumps(key, ensure_ascii=True))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self.unknown_keys(child, f'{path}[{index}]')

    def yaml(self):
        raw = self.read('recovery.yaml', required=self.all_fields)
        if raw is None:
            return
        try:
            # Avoid recursive alias graphs and implicit merge precedence.
            for token in yaml.scan(raw):
                if isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken)):
                    raise InvalidData()
            data = yaml.load(raw, Loader=Loader)
        except (yaml.YAMLError, InvalidData, UnicodeError, ValueError):
            self.error('recovery/recovery.yaml', 'invalid YAML; use unique string keys without aliases, anchors or custom tags')
            return
        root = self.mapping(data, 'recovery/recovery.yaml',
                            {'schema_version', 'kubernetes', 'application_credentials', 'database_backups'},
                            {'schema_version', 'application_credentials'} if self.all_fields else {'schema_version'})
        if type(root.get('schema_version')) is not int or root.get('schema_version') != 1:
            self.error('recovery/recovery.yaml.schema_version', 'must be integer 1')
        if 'database_backups' in root:
            self.database_backups(root['database_backups'])
        self.coordinator_inputs(root.get('database_backups'))
        if 'kubernetes' in root:
            kube = self.mapping(root['kubernetes'], 'kubernetes', {'nonprod'})
            if 'nonprod' in kube:
                nonprod = self.mapping(kube['nonprod'], 'kubernetes.nonprod', {'sealed_secrets_controller_keys'})
                if 'sealed_secrets_controller_keys' in nonprod:
                    self.controllers(nonprod['sealed_secrets_controller_keys'])
        if 'application_credentials' in root:
            apps = self.mapping(root['application_credentials'], 'application_credentials', {'dev', 'stage', 'prod'})
            for env in ('dev', 'stage', 'prod'):
                if env in apps:
                    self.application(apps[env], env)

    def database_backups(self, value):
        loc = 'database_backups'
        keys = {'account_id', 'api_token', 'endpoint', 'jurisdiction', 'region',
                'bucket', 'access_key_id', 'secret_access_key'}
        item = self.mapping(value, loc, keys, keys - {'api_token'})
        for key, val in item.items():
            if key in keys:
                self.text(val, loc + '.' + key)
        for key, length in [('account_id', 32), ('access_key_id', 32), ('secret_access_key', 64)]:
            if not isinstance(item.get(key), str) or not re.fullmatch('[a-fA-F0-9]{' + str(length) + '}', item[key]):
                self.error(loc + '.' + key, 'expected Cloudflare hexadecimal credential identifier of length ' + str(length))
        jurisdiction = item.get('jurisdiction')
        if jurisdiction not in ['default', 'eu', 'fedramp']:
            self.error(loc + '.jurisdiction', 'must be default, eu or fedramp')
        suffix = '' if jurisdiction == 'default' else '.' + str(jurisdiction)
        expected = 'https://' + str(item.get('account_id')) + suffix + '.r2.cloudflarestorage.com'
        if item.get('endpoint') != expected:
            self.error(loc + '.endpoint', 'must match the account and jurisdiction HTTPS S3 endpoint, without a path')
        if item.get('bucket') != 'liora-backup':
            self.error(loc + '.bucket', 'must be the dedicated liora-backup bucket')
        if item.get('region') != 'auto':
            self.error(loc + '.region', 'must be auto for R2 S3 access')

    def coordinator_inputs(self, reference):
        raw = self.read('backup-coordinator.json', required=False)
        if raw is None:
            return
        loc = 'recovery/backup-coordinator.json'
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            self.error(loc, 'invalid JSON')
            return
        data = self.mapping(data, loc, {'version', 'state_dir', 'listen', 'r2', 'clusters'})
        if data.get('version') != 1 or type(data.get('version')) is not int:
            self.error(loc + '.version', 'must be integer 1')
        if data.get('state_dir') != '/var/lib/liora-backups' or data.get('listen') != '192.168.77.250':
            self.error(loc, 'must use the configured VM 250 listener and state directory')
        r2 = self.mapping(data.get('r2'), loc + '.r2', {'endpoint','bucket','access_key_id','secret_access_key'})
        if not isinstance(reference, dict) or any(r2.get(k) != reference.get(k) for k in r2):
            self.error(loc + '.r2', 'must match database_backups recovery inputs')
        clusters = self.mapping(data.get('clusters'), loc + '.clusters', {'nonprod','prod'})
        for cluster, vip, admin in [('nonprod','192.168.77.11','192.168.77.16'),('prod','192.168.77.12','192.168.77.17')]:
            path = loc + '.clusters.' + cluster
            profile = self.mapping(clusters.get(cluster), path, {'server','token','ca_pem','alertmanager'})
            if profile.get('server') != 'https://' + vip + ':6443' or profile.get('alertmanager') != 'http://' + admin + ':9093':
                self.error(path, 'server or Alertmanager does not match this cluster')
            if self.text(profile.get('ca_pem'), path + '.ca_pem'):
                try:
                    with warnings.catch_warnings(record=True) as recorded:
                        warnings.simplefilter('always')
                        x509.load_pem_x509_certificate(profile['ca_pem'].encode())
                    if recorded:
                        self.warn(path + '.ca_pem', 'cluster CA has a legacy X509 encoding accepted by current cryptography; retain the original CA')
                except (ValueError, TypeError):
                    self.error(path + '.ca_pem', 'expected a PEM cluster CA certificate')
            if self.text(profile.get('token'), path + '.token'):
                try:
                    parts = profile['token'].split('.')
                    if len(parts) != 3 or any(not re.fullmatch('[A-Za-z0-9_-]+', part) for part in parts):
                        raise ValueError()
                    payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=' * (-len(parts[1]) % 4)))
                    if payload.get('sub') != 'system:serviceaccount:cnpg-system:backup-coordinator':
                        raise ValueError()
                    if 'exp' in payload and payload['exp'] <= datetime.datetime.now(datetime.timezone.utc).timestamp():
                        raise ValueError()
                except (ValueError, TypeError, KeyError):
                    self.error(path + '.token', 'expected an unexpired coordinator service-account JWT; signature checked by the API')

    def controllers(self, entries):
        path = 'kubernetes.nonprod.sealed_secrets_controller_keys'
        if not isinstance(entries, list) or not entries:
            self.error(path, 'must be a nonempty list')
            return
        names = set()
        for i, entry in enumerate(entries):
            loc = f'{path}[{i}]'
            item = self.mapping(entry, loc, {'secret_name', 'tls_crt_pem', 'tls_key_pem'})
            name = item.get('secret_name')
            if self.text(name, loc + '.secret_name'):
                if len(name) > 253 or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', name) or any(
                        not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', p) for p in name.split('.')):
                    self.error(loc + '.secret_name', 'must be a Kubernetes DNS subdomain, at most 253 characters')
                if name in names:
                    self.error(loc + '.secret_name', 'duplicate controller Secret name')
                names.add(name)
            cert_text, key_text = item.get('tls_crt_pem'), item.get('tls_key_pem')
            cert_ok = self.text(cert_text, loc + '.tls_crt_pem')
            key_ok = self.text(key_text, loc + '.tls_key_pem')
            if not (cert_ok and key_ok):
                continue
            try:
                cert = x509.load_pem_x509_certificate(cert_text.encode())
                key = serialization.load_pem_private_key(key_text.encode(), password=None)
                if not isinstance(key, rsa.RSAPrivateKey):
                    raise ValueError()
                fmt = (serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
                if cert.public_key().public_bytes(*fmt) != key.public_key().public_bytes(*fmt):
                    raise ValueError()
                now = datetime.datetime.now(datetime.timezone.utc)
                # cryptography 41 has only the naïve properties; 42+ provides UTC.
                if hasattr(cert, 'not_valid_before_utc'):
                    before, after = cert.not_valid_before_utc, cert.not_valid_after_utc
                else:
                    before = cert.not_valid_before.replace(tzinfo=datetime.timezone.utc)
                    after = cert.not_valid_after.replace(tzinfo=datetime.timezone.utc)
                # Expired historical keys are still necessary for decryption.
                if not before <= now <= after:
                    self.warn(loc + '.tls_crt_pem', 'certificate is outside its validity period; retain historical decryption keys')
                if key.key_size < 2048:
                    self.warn(loc + '.tls_key_pem', 'RSA key is shorter than 2048 bits')
            except (ValueError, TypeError, OverflowError, UnsupportedAlgorithm):
                self.error(loc, 'expected a PEM certificate and matching unencrypted RSA private key')

    def application(self, value, env):
        loc = 'application_credentials.' + env
        app = self.mapping(value, loc, {'namespace', 'first_superuser', 'backend-secrets', 'db-secrets'})
        if app.get('namespace') != 'app-' + env:
            self.error(loc + '.namespace', 'must match the environment namespace app-' + env)
        email = app.get('first_superuser')
        if self.text(email, loc + '.first_superuser'):
            try:
                if len(email) > 255:
                    raise EmailNotValidError()
                validate_email(email, check_deliverability=False)
                if email != 'admin007@liora.aprt.info':
                    self.error(loc + '.first_superuser', 'must match the initial account configured in runbook 13 and the application ConfigMaps')
            except EmailNotValidError:
                self.error(loc + '.first_superuser', 'must be an application EmailStr, at most 255 characters')
        backend = self.mapping(app.get('backend-secrets'), loc + '.backend-secrets',
                               {'SECRET_KEY', 'FIRST_SUPERUSER_PASSWORD', 'POSTGRES_PASSWORD', 'SMTP_PASSWORD'})
        db = self.mapping(app.get('db-secrets'), loc + '.db-secrets', {'POSTGRES_PASSWORD'})
        for name, val in backend.items():
            if name not in {'SECRET_KEY', 'FIRST_SUPERUSER_PASSWORD', 'POSTGRES_PASSWORD', 'SMTP_PASSWORD'}:
                continue
            field = loc + '.backend-secrets.' + name
            if not self.text(val, field, empty=name == 'SMTP_PASSWORD'):
                continue
            if name == 'FIRST_SUPERUSER_PASSWORD' and not 8 <= len(val) <= 40:
                self.error(field, 'must contain 8 to 40 characters (application UserCreate constraint)')
            if name == 'SECRET_KEY' and len(val.encode()) < 32:
                self.warn(field, 'signing key has fewer than 32 UTF-8 bytes; use a strong random key')
        if 'POSTGRES_PASSWORD' in db:
            self.text(db['POSTGRES_PASSWORD'], loc + '.db-secrets.POSTGRES_PASSWORD')
            if db['POSTGRES_PASSWORD'] != backend.get('POSTGRES_PASSWORD'):
                self.error(loc + '.db-secrets.POSTGRES_PASSWORD', 'must equal backend-secrets.POSTGRES_PASSWORD')

    def ssh(self):
        private = self.read('LIORA-id_ed25519')
        public = self.read('LIORA-id_ed25519.pub', private=False)
        if private is None or public is None:
            return
        try:
            key = serialization.load_ssh_private_key(private, password=None)
            declared = serialization.load_ssh_public_key(public)
            fmt = (serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
            if not isinstance(key, ed25519.Ed25519PrivateKey) or key.public_key().public_bytes(*fmt) != declared.public_bytes(*fmt):
                raise ValueError()
        except (ValueError, TypeError, UnsupportedAlgorithm):
            self.error('recovery/LIORA-id_ed25519[.pub]', 'expected matching unencrypted OpenSSH Ed25519 keys')

    def tokens(self):
        for name in ('k3s-dev-stage.token', 'k3s-prod.token'):
            raw = self.read(name, required=False)
            if raw is not None and not re.fullmatch(rb'[A-Za-z0-9]{64}\n?', raw):
                self.error('recovery/' + name, 'expected the 64-character alphanumeric token generated by Ansible')
        for name in ('k3s-nonprod-server.token', 'k3s-prod-server.token'):
            raw = self.read(name, required=False)
            if raw is not None and not re.fullmatch(rb'K10[0-9a-f]{64}::server:[^\r\n\x00]+\n?', raw):
                self.error('recovery/' + name, 'expected the original secure K3s server token copied from the running cluster')

    def probe(self, values):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        url = values['TF_VAR_pm_endpoint'].rstrip('/') + '/api2/json/nodes/' + urllib.parse.quote(values['TF_VAR_pm_node'], safe='') + '/qemu/9013/config'
        request = urllib.request.Request(url, headers={'Authorization': 'PVEAPIToken=' + values['TF_VAR_pm_api_token']})
        try:
            # Lab Proxmox uses a self-signed certificate; never follow redirects.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                                 urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
            with opener.open(request, timeout=15) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
        except Exception:
            self.error('Proxmox API', 'connection failed; use --offline for local validation only')
            return
        if status == 200:
            print('OK: Proxmox API token can read template 9013 (HTTP 200)')
        else:
            self.error('Proxmox API', f'template 9013 read failed (HTTP {int(status)})')


def main(args):
    allowed = {'--all', '--tailscale', '--offline', '--strict-warnings', '--help'}
    if any(arg not in allowed for arg in args) or ('--all' in args and '--tailscale' in args):
        print('Usage: check_credentials.sh [--all|--tailscale] [--offline] [--strict-warnings]', file=sys.stderr)
        return 2
    if '--help' in args:
        print('Usage: check_credentials.sh [--all|--tailscale] [--offline] [--strict-warnings]\n'
              'Exit: 0 valid (warnings allowed); 1 invalid or strict warnings; 2 usage/dependency/internal error.\n'
              'See recovery/README.md for scope and supported fields. No data is modified.')
        return 0
    check = Check(os.environ.get('RECOVERY_DIR', Path(__file__).resolve().parent), '--tailscale' not in args)
    values = check.env()
    check.ssh()
    check.yaml()
    check.tokens()
    if '--offline' in args:
        print('INFO: Live Proxmox check skipped (--offline); provider permissions and expiry are unverified.')
    elif check.errors == 0:
        check.probe(values)
    else:
        print('INFO: Live Proxmox check skipped because local validation failed.')
    failed = check.errors > 0 or ('--strict-warnings' in args and check.warnings > 0)
    print(f'Credential check: {check.errors} error(s), {check.warnings} warning(s); exit {int(failed)}.')
    return int(failed)


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception:
        # Never print exception messages, parser context, HTTP bodies or tracebacks.
        print('ERROR: Credential validation could not complete; check file types and dependencies. Exit 2.', file=sys.stderr)
        sys.exit(2)
