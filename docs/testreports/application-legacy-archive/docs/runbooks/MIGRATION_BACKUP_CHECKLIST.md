# Recovery and backup checklist

2026-10-09 UTC. Minikube was deleted by the operator before this rebuild. Do not recreate it.

| Item | Found / recoverable | Action |
| --- | --- | --- |
| Sealed Secrets private key | `sealed-secrets-key-backup.yaml`, one kube-system key Secret | Restricted to 0600, excluded from Git; restored into kind before controller startup |
| Key validation | Certificate SHA256 `0B:89:57:D5:50:6D:48:76:16:B6:FD:8A:2D:74:D8:9A:49:12:59:95:4A:6D:57:C9:AB:18:0D:A8:0C:E2:22:7B` | Offline recovery of backend/database ciphertext succeeded; live app-dev decryption succeeded |
| Legacy encrypted backend/database secrets | `k8s/overlays/dev/sealed-secret-{backend,db}.yaml` | Recovered only in memory; resealed for app-dev in `infra/kind/secrets/app-dev/` |
| Legacy frontend SealedSecret | Empty file | No encrypted content; initial kubeseal success on empty input was not a meaningful test. Active frontend has no frontend Secret dependency |
| GHCR access | Existing host `~/.docker/config.json` contains ghcr.io auth | Only that registry entry restored to app-dev/app-stage; no credentials printed or committed. Anonymous access is unauthorized |
| STAGE backend/database secrets | Fresh credentials created with explicit user authorization | Encrypted SealedSecrets saved in infra/kind/secrets/app-stage; passwords match and differ from DEV. Admin password fits the application 40-character maximum. No plaintext files or values printed |
| STAGE TLS | No backup identified; standard overlay references app-tls | Local kind HTTP override removes this dependency; preserve HTTPS/TLS design for later proper certificate provisioning |
| Argo repository credentials | No backup identified | Public Git repository main is accessible; supply read-only access if made private |
| Jenkins home | No archive identified; host Jenkins inactive/not installed | Old controller jobs/plugins/credentials/build history cannot be recovered from Git alone |
| PostgreSQL data | Old PVC data gone, no dump identified | Intentionally disposable: new PVCs/init/migrations recreate test databases; old rows are not restored |
| Monitoring data | Previous rollout paused; no monitoring PVC observed in historical report | Recreate short-retention history when rollout is safe |

Do not commit private material. `.migration-backup/`, `.tools/`, and `sealed-secrets-key-backup.yaml` are ignored. Existing private PEM in `.migration-backup/` is 0600 within a 0700 directory. Store an additional encrypted/off-host copy of the key; the ignored working copy alone is not disaster recovery. No private key or plaintext secret values were printed.

For another engineer, securely supply the key backup, package-reader registry access and namespace-specific application secrets. Run `infra/kind/scripts/recover-dev-secrets.py` to regenerate encrypted app-dev Secrets from the old ciphertext/key. Restoring the key alone cannot recreate live-only STAGE/registry/TLS credentials.

Future key export (run against kind, outside a build log):

```bash
umask 077
mkdir -p .migration-backup
chmod 700 .migration-backup
kubectl --context kind-fastapi-dev get secret -n kube-system \
  -l sealedsecrets.bitnami.com/sealed-secrets-key -o yaml \
  > .migration-backup/sealed-secrets-keys.yaml
chmod 600 .migration-backup/sealed-secrets-keys.yaml
```

Export every key after rotation; retain older keys needed by ciphertext. Do not print/cat these files.

Future Jenkins backup: put the controller in quiet mode, wait for running builds, stop the controller for a consistent backup, and archive all of `JENKINS_HOME` (jobs, plugins, credentials.xml, secrets/master.key, secrets/hudson.util.Secret, users, config.xml, build archives). Encrypt the archive and preserve ownership. Credentials require the matching Jenkins encryption files. Restart after backup. No such old backup was found; none was fabricated.

Jenkins follow-up: discovered /home/root-admin/jenkins-values.yaml and cached jenkins-5.9.56.tgz. Preserved copies under ignored .migration-backup/jenkins (0700 directory/0600 files). These recover partial install settings/chart, not JENKINS_HOME, jobs/history/plugin inventory or encrypted credentials. The remaining Docker volume belongs to current kind and was left untouched. See ../../dev-journal/reports/JENKINS_RECOVERY_REPORT.md.
