# Restore a K3s etcd snapshot

**Tools:** Python 3, `jq`, SSH/SCP, curl and the pinned K3s binary.
**Use for:** Recover one existing three-server K3s datastore.
**Do not use for:** Fresh cluster bootstrap or application database recovery alone.
**Standard route:** [Rebuild infrastructure and restore application data](../01-Disaster_recovery.md). This runbook is optional.
**Effect:** Replaces Kubernetes metadata, Secrets and controller settings with snapshot state. It does not restore PVC files.

## Preconditions

- [ ] Get console/root access to all three selected servers.
- [ ] Obtain the matching snapshot, original server token, three node passwords and recovery-set manifest.
- [ ] Obtain the original node names, addresses and K3s version from the manifest.
- [ ] Preserve surviving local disks. Stop if a storage plan would delete existing data.
- [ ] Hold reachable automation using [24](24-hold-surviving-automation.md).
- [ ] Stop external Jenkins/promotion processes that can write to this cluster.
- [ ] Select **one** cluster below. Keep the other cluster unchanged.

| Cluster | First server | Other servers | API VIP | Node names |
| --- | --- | --- | --- | --- |
| NONPROD | 192.168.77.201 | .202, .203 | 192.168.77.11 | k3s-1-01, k3s-1-02, k3s-1-03 |
| PROD | 192.168.77.211 | .212, .213 | 192.168.77.12 | k3s-2-01, k3s-2-02, k3s-2-03 |

**Stop:** Missing original token, wrong cluster identity, an unfenced old server,
unknown snapshot integrity, or no plan for existing volume data. Do not run
`site.yml`, generate a new server token or create a fresh datastore for this route.

## 1. Prepare a recovery set

Routine scheduling, retention and failure response: [etcd backups](../docs/operations/ETCD_BACKUPS.md).

**Where:** Trusted operator machine, infrastructure repository root. Keep all snapshot work in private `.local-work/` directories, never `recovery/`.

### Select an R2 snapshot

Choose this route for an off-host snapshot. Use one source route only; do not
also overwrite it with the local export below.

- [ ] Recover the fixed original token and matching node-identity metadata from the encrypted private kit. NONPROD uses `recovery/k3s-nonprod-server.token`; PROD uses `recovery/k3s-prod-server.token`.
- [ ] List this cluster's R2 snapshots:

```sh
cluster=nonprod
bash scripts/local-python.sh scripts/backups/etcd_r2.py list --cluster "$cluster"
```

Standalone tool: [etcd_r2.py](../scripts/backups/etcd_r2.py).

- [ ] Select the snapshot `name` field and matching private set. Use a new output directory:

```sh
read -r -p 'Exact R2 snapshot filename: ' snapshot
read -r -p 'Matching node-identity metadata directory: ' identity_set
recovery_set="$PWD/.local-work/etcd-restore/$cluster-incident-1"
bash scripts/local-python.sh scripts/backups/etcd_r2.py download \
  --cluster "$cluster" --snapshot "$snapshot" --identity-set "$identity_set" \
  --output "$recovery_set"
```

Standalone tool: [etcd_r2.py](../scripts/backups/etcd_r2.py).

**Expected:** Exit 0, ZIP/embedded-checksum success and a complete recovery set.
The helper uses the fixed token path for this cluster and checks it against the
selected identity metadata and snapshot. It copies a token only into this
incident restore bundle, not for routine backups. It preserves the source kit.
For a rotated historical token, add `--token-file <preserved-token-path>`.

**Stop:** Metadata or checksum mismatch. Keep the file private; select the token
set that applied when the snapshot was created. Do not substitute a new token.

Continue at **Check and copy the selected set** below.

### Alternative: capture from reachable servers

- [ ] Select a new private output directory and a verified SSH host-key file:

```sh
umask 077
cluster=nonprod
recovery_set="$PWD/.local-work/etcd-restore/$cluster-incident-1"
known_hosts="$HOME/.ssh/known_hosts"
python3 scripts/recovery/export-k3s-recovery.py \
  --cluster "$cluster" --known-hosts "$known_hosts" --output "$recovery_set"
```

Standalone tool: [export-k3s-recovery.py](../scripts/recovery/export-k3s-recovery.py).

The tool reads the latest existing local snapshot on the first server, its
original token and all three node passwords. It changes no server. Use the
verified host-key file for these nodes; do not disable host-key checks.

**Expected:** Exit 0 and `complete: true`. The new directory contains
`manifest.json`, `server.token`, one snapshot and `nodes/<node>/password`.

**If export fails:** Keep the partial directory. Fix source access or token
mismatch. Export to a new directory. A directory without a complete manifest
is not a recovery set.

### Check and copy the selected set

- [ ] Check hashes and private permissions:

```sh
python3 scripts/recovery/verify-k3s-recovery.py "$recovery_set"
```

Standalone tool: [verify-k3s-recovery.py](../scripts/recovery/verify-k3s-recovery.py).

**Expected:** Exit 0, matching hashes and a complete three-node set. This checks
file integrity; it does not decrypt the snapshot.

- [ ] Record the snapshot time and K3s version from `manifest.json`. Confirm the snapshot precedes the incident that damaged the datastore.
- [ ] Keep the original set unchanged. Copy it and the hold helper to the first server:

```sh
first=192.168.77.201
known_hosts="$HOME/.ssh/known_hosts"
ssh -i recovery/LIORA-id_ed25519 -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$known_hosts" "root-admin@$first" \
  'install -d -m 700 "$HOME/k3s-recovery"'
scp -i recovery/LIORA-id_ed25519 -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$known_hosts" -r "$recovery_set" \
  scripts/recovery/hold-restored-workloads.py "root-admin@$first:k3s-recovery/"
```

- [ ] Substitute `.211` for PROD. Keep paths and host keys consistent in later SSH/SCP commands.
- [ ] Copy the same protected recovery set to each peer. Repeat these commands with the other peer's address:

```sh
peer=192.168.77.202
ssh -i recovery/LIORA-id_ed25519 -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$known_hosts" "root-admin@$peer" \
  'install -d -m 700 "$HOME/k3s-recovery"'
scp -i recovery/LIORA-id_ed25519 -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$known_hosts" -r "$recovery_set" \
  "root-admin@$peer:k3s-recovery/"
```

Use `.202` and `.203` for NONPROD; `.212` and `.213` for PROD.
Install only each node's own password in step 5.
- [ ] Keep fixed tokens and node metadata in the existing encrypted recovery archive using [recovery inputs](../recovery/README.md#k3s-server-tokens-and-recovery-identities). Snapshots stay in native R2 storage. Do not add this incident snapshot bundle to `recovery/` or copy tokens for routine snapshots.

## 2. Stop every server and its workloads

**Where:** Console/root shell on **each** selected server, one at a time.

```sh
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
```

- [ ] Record the node name and installed K3s version:

```sh
hostname
/usr/local/bin/k3s --version
```

- [ ] Require the original node name and the manifest's K3s version.
- [ ] Stop K3s and its remaining container processes:

```sh
systemctl stop k3s
/usr/local/bin/k3s-killall.sh
systemctl is-active k3s
pgrep -a -f '[c]ontainerd-shim' || true
```

**Expected:** K3s is inactive; no `containerd-shim` processes remain. Stopping
only the systemd service does not stop all existing containers.

- [ ] Finish this step on all three nodes before step 3.
- [ ] Power off or fence any unreachable old node at Proxmox. Do not let it rejoin with stale datastore state.

**Replacement machine:** After copying the recovery set, install its exact K3s
version without starting the service. Run on the replacement node as root:

```sh
set_dir=/home/root-admin/k3s-recovery/nonprod-incident-1
k3s_version=$(jq -r '.k3s_version | split(" ")[2]' "$set_dir/manifest.json")
curl --fail --silent --show-error --location https://get.k3s.io -o /root/install-k3s.sh
INSTALL_K3S_VERSION="$k3s_version" INSTALL_K3S_SKIP_START=true \
  sh /root/install-k3s.sh server
/usr/local/bin/k3s --version
```

Use the selected set's actual path. Require the displayed version to match the
manifest. Do not run the Ansible fresh-cluster plays.

## 3. Prepare the first server without an agent

**Where:** First server, root shell. Other servers remain stopped.

- [ ] Set the selected recovery-set path and node addresses:

```sh
set_dir=/home/root-admin/k3s-recovery/nonprod-incident-1
node_name=k3s-1-01
node_ip=192.168.77.201
api_vip=192.168.77.11
incident=incident-1
snapshot=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["snapshot"])' "$set_dir/manifest.json")
```

For PROD use its copied set, `k3s-2-01`, `.211` and `.12`.

- [ ] Preserve the current configuration and datastore before reset:

```sh
test ! -e "/root/k3s-before-$incident/config" || { echo "Stop: preserved configuration exists" >&2; exit 1; }
install -d -m 700 "/root/k3s-before-$incident"
df -h /root /var/lib/rancher/k3s
du -sh /var/lib/rancher/k3s/server/db
cp -a /etc/rancher/k3s "/root/k3s-before-$incident/config"
cp -a /var/lib/rancher/k3s/server/db "/root/k3s-before-$incident/db"
```

On an empty replacement node, omit only a source path that does not exist.
Require enough free disk space before copying. Keep previous evidence; use a new
incident suffix if the destination already exists.

- [ ] If native R2 backup configuration exists, move its drop-in into the preserved directory. This keeps the restore from uploading/pruning snapshots before release:

```sh
test ! -f /etc/rancher/k3s/config.yaml.d/90-etcd-r2.yaml || \
  mv /etc/rancher/k3s/config.yaml.d/90-etcd-r2.yaml "/root/k3s-before-$incident/90-etcd-r2.yaml"
```

- [ ] Install the original token and this node's password:

```sh
install -d -m 700 /etc/rancher/k3s /etc/rancher/node
install -m 600 "$set_dir/server.token" /etc/rancher/k3s/recovery-server.token
install -m 600 "$set_dir/nodes/$node_name/password" /etc/rancher/node/password
```

- [ ] Replace only the K3s configuration with this restore configuration:

```sh
umask 077
cat > /etc/rancher/k3s/config.yaml <<EOF
cluster-init: true
node-name: $node_name
node-ip: $node_ip
token-file: /etc/rancher/k3s/recovery-server.token
tls-san:
  - $api_vip
disable-agent: true
etcd-disable-snapshots: true
etcd-s3: false
EOF
chmod 600 /etc/rancher/k3s/config.yaml
```

- [ ] Compare the preserved configuration and systemd unit. Carry forward any required non-default datastore/CNI/service-CIDR options. Remove conflicting inline `--server`, `--token`, reset flags or environment overrides. The repository baseline uses Flannel and the default Pod/Service CIDRs; do not change them.
- [ ] Inspect `/etc/rancher/k3s/config.yaml.d/`, `/etc/systemd/system/k3s.service` and its environment files privately. Stop if an override would start an agent or select another datastore.

## 4. Restore the snapshot and hold recovered workloads

**Where:** First server, root shell.

- [ ] Run the one-time reset. Keep the log private:

```sh
umask 077
/usr/local/bin/k3s server --cluster-reset \
  --cluster-reset-restore-path="$set_dir/$snapshot" --etcd-s3=false \
  > "/root/k3s-before-$incident/reset.log" 2>&1
```

**Expected:** Exit 0 and a log message that the managed etcd cluster membership
has been reset. The server exits after reset.

**If reset fails:** Keep all servers stopped. Inspect the private log. Check the
snapshot checksum, original token, disk space and exact K3s version. Do not delete
the reset flag or repeatedly reset an unknown state.

- [ ] Start only the first server in agentless mode:

```sh
systemctl start k3s
/usr/local/bin/k3s kubectl --request-timeout=20s get --raw=/readyz
```

**Expected:** API returns `ok`. Use the local kubeconfig; API VIP Pods are not
running yet. Wait up to five minutes, inspecting `journalctl -u k3s` privately
if needed. Stop if API readiness does not recover.

- [ ] Save original workload settings and apply the recovery hold:

```sh
python3 /home/root-admin/k3s-recovery/hold-restored-workloads.py \
  --manifest "$set_dir/manifest.json" \
  --state "/root/k3s-before-$incident/workload-hold.json" \
  --confirm-all-agents-stopped
```

Standalone tool: [hold-restored-workloads.py](../scripts/recovery/hold-restored-workloads.py).

**Expected:** Exit 0 and `held: true`. The helper checks the cluster UID, records
original settings before changes, disables Argo automatic sync, scales all
Deployments/StatefulSets to zero and suspends Jobs/CronJobs. It deletes old
non-DaemonSet/non-mirror workload Pod objects using UID preconditions. It keeps
PVCs, PVs, Secrets, namespaces and DaemonSets unchanged.

**If interrupted:** Keep agents off. Rerun the same command with `--resume` and
the same state file. Do not remove or replace the state file: it contains the
original settings. Copy it into the protected incident recovery archive.

## 5. Rejoin the other servers without agents

**Where:** Root shell on each peer, one at a time. First server stays running.

- [ ] Set this peer's identity:

```sh
set_dir=/home/root-admin/k3s-recovery/nonprod-incident-1
incident=incident-1
node_name=k3s-1-02
node_ip=192.168.77.202
first=192.168.77.201
api_vip=192.168.77.11
```

- [ ] Preserve this peer's current configuration before changing it:

```sh
test ! -e "/root/k3s-before-$incident/config" || { echo "Stop: preserved configuration exists" >&2; exit 1; }
install -d -m 700 "/root/k3s-before-$incident"
cp -a /etc/rancher/k3s "/root/k3s-before-$incident/config"
test ! -f /etc/rancher/k3s/config.yaml.d/90-etcd-r2.yaml || \
  mv /etc/rancher/k3s/config.yaml.d/90-etcd-r2.yaml "/root/k3s-before-$incident/90-etcd-r2.yaml"
```

Stop if the incident directory already contains a preserved configuration. Use a
new incident suffix; do not overwrite the earlier copy.

- [ ] Install the original token, this peer's password and agentless configuration:

```sh
install -d -m 700 /etc/rancher/k3s /etc/rancher/node
install -m 600 "$set_dir/server.token" /etc/rancher/k3s/recovery-server.token
install -m 600 "$set_dir/nodes/$node_name/password" /etc/rancher/node/password
umask 077
cat > /etc/rancher/k3s/config.yaml <<EOF
server: https://$first:6443
node-name: $node_name
node-ip: $node_ip
token-file: /etc/rancher/k3s/recovery-server.token
tls-san:
  - $api_vip
disable-agent: true
etcd-disable-snapshots: true
etcd-s3: false
EOF
```

Use `k3s-1-03`/`.203` on the other NONPROD peer. For PROD use
`k3s-2-02`/`.212` and `k3s-2-03`/`.213`, first `.211`, VIP `.12` and the PROD set.
Check systemd/config overrides as in step 3.
- [ ] Move the old peer datastore aside; never delete it:

```sh
mv /var/lib/rancher/k3s/server/db "/var/lib/rancher/k3s/server/db.before-$incident"
systemctl start k3s
/usr/local/bin/k3s kubectl --request-timeout=20s get --raw=/readyz
```

On an empty replacement peer, omit only the `mv` of the absent directory. Stop
if the destination exists. Do not reset a peer or copy the first server's old
member database to it.

**Expected:** Peer joins the restored datastore and its local API returns `ok`.
Finish the second server before starting the third. Inspect private K3s logs
if a peer cannot join; leave workload agents off until all three APIs are ready.

## 6. Return node agents and verify the cluster

**Where:** Root shell on each selected server, first server then peers.

- [ ] Change `disable-agent: true` to `disable-agent: false` in the restore configuration:

```sh
sed -i 's/^disable-agent: true$/disable-agent: false/' /etc/rancher/k3s/config.yaml
systemctl restart k3s
/usr/local/bin/k3s kubectl --request-timeout=20s get nodes -o wide
```

- [ ] Wait for each node to become Ready before restarting the next node.
- [ ] Require three Ready nodes with original names and addresses. Keep all application/CNPG/Jenkins workloads held.
- [ ] On the first server, check the API VIP DaemonSet and its endpoint:

```sh
/usr/local/bin/k3s kubectl -n kube-system get daemonsets,pods -o wide
/usr/local/bin/k3s kubectl --server="https://$api_vip:6443" \
  --request-timeout=20s get --raw=/readyz
```

- [ ] Once the VIP returns `ok`, change peers' `server:` address from the first-node IP to `https://<api-vip>:6443`. Restart one peer at a time; require Ready after each restart.
- [ ] Recover administrator kubeconfigs using [09, kubeconfig retrieval](09-install-k3s-clusters.md#if-only-kubeconfig-retrieval-fails). Do not rerun installation/bootstrap plays.

## 7. Release workloads by storage and dependency

**Where:** First server, root shell; then the operator machine for linked procedures.

- [ ] List the saved original controller replicas:

```sh
jq -r '.resources[] | select(has("replicas")) | [.namespace,.kind,.name,.replicas] | @tsv' \
  "/root/k3s-before-$incident/workload-hold.json"
```

- [ ] Restore CoreDNS first. Use its saved namespace, kind/name and replica count:

```sh
/usr/local/bin/k3s kubectl -n kube-system scale deployment/coredns --replicas=1
/usr/local/bin/k3s kubectl -n kube-system rollout status deployment/coredns --timeout=5m
```

Use the saved count if it differs. Release other controllers individually using
`kubectl -n <namespace> scale <kind>/<name> --replicas=<saved-count>` and check
rollout status. Do not scale every controller from a loop.

- [ ] Check PV node affinity, bound PVCs and actual data directories on the named nodes:

```sh
/usr/local/bin/k3s kubectl get pv
/usr/local/bin/k3s kubectl get pvc -A
/usr/local/bin/k3s kubectl get pv <selected-pv> -o yaml
```

- [ ] On each PV's node, inspect its listed local/hostPath directory using `stat` and `du -sh`. Require the original volume contents before starting its consumer.

**If local-path data was lost:** Keep CNPG, Jenkins and other volume consumers
stopped. Do not create an empty directory at the old path. A restored etcd
snapshot cannot reconstruct those files. Use the fresh-cluster recovery route
in [01](../01-Disaster_recovery.md), [20](20-restore-live-postgresql.md) and
[23](23-restore-jenkins-controller.md); retain this datastore and its metadata
until a separate replacement plan is approved. Runbook 20 refuses existing
Cluster/PVC objects and does not retire them automatically.

- [ ] Restore platform operators and monitoring only after their required configuration/storage is available. Keep Argo and Jenkins held.
- [ ] Restore CNPG operator replicas only after database volume contents and database recovery scope are established. Check each environment using [18, database checks](18-cloudnative-pg.md#4-verify-database-and-application).
- [ ] Restore application Deployments with saved counts and unchanged digests. Follow [20, application checks](20-restore-live-postgresql.md#4-reconcile-desired-state-before-opening-application-traffic) for rollout, HTTPS, login and CRUD checks. Do not run prestart before the database/schema gate.
- [ ] Restore Jenkins only through [23](23-restore-jenkins-controller.md), under its execution hold.
- [ ] Before restoring Argo controller replicas, inspect Applications for pending operations:

```sh
/usr/local/bin/k3s kubectl -n argocd get applications \
  -o custom-columns='NAME:.metadata.name,PENDING:.operation,PHASE:.status.operationState.phase'
```

- [ ] If `PHASE` is `Running`, first request termination for that selected Application:

```sh
/usr/local/bin/k3s kubectl -n argocd patch application <application-name> \
  --type=merge -p '{"status":{"operationState":{"phase":"Terminating"}}}'
```

- [ ] If `PENDING` is not empty, remove that selected pending request before starting the controller:

```sh
/usr/local/bin/k3s kubectl -n argocd patch application <application-name> \
  --type=json -p '[{"op":"remove","path":"/operation"}]'
```

Recheck the list. Keep the controller stopped if the selected resource changes
or the patch fails. Compare the recovered revision with remote Git before release.
- [ ] Restore Argo components, then compare diffs and release child policies before roots using [14](14-install-argocd.md#4-adopt-manually-then-review-automation).
- [ ] Review each saved Job/CronJob before restoring its recorded suspend state. Leave obsolete work suspended. Restore only approved Jenkins triggers using [17](17-install-operate-jenkins.md#4-activate-delivery).
- [ ] Check the backup coordinator fence and recovered Backup objects before resuming its timer using [19](19-cnpg-r2-backup-pitr.md#2-install-the-coordinator-on-vm-250).

## 8. Close the datastore recovery

- [ ] Require all three nodes Ready, the API VIP usable and restored controllers healthy.
- [ ] Reapply [native etcd backup configuration](../docs/operations/ETCD_BACKUPS.md#configure-or-reapply-native-backups) only after application/storage checks pass. Confirm new local and R2 snapshots before releasing backup operation.
- [ ] Require application data/HTTPS/login/CRUD and backup checks complete.
- [ ] Confirm unrelated jobs remain disabled and the PROD image-promotion acceptance gate remains enforced.
- [ ] Keep the original recovery set, reset log, displaced datastore directories and hold-state file until incident retention permits removal.
- [ ] Record snapshot identity/time, selected token set, restored cluster UID, node identities, restored volume sources and automation release in the incident report. Do not record token/password values.

**Complete:** The datastore has three working server members; volume consumers
use recovered data; application checks pass; only approved automation has resumed.

## References

- [K3s snapshot restore and original-token requirements](https://docs.k3s.io/datastore/backup-restore)
- [K3s local snapshot restore and peer rejoin](https://docs.k3s.io/cli/etcd-snapshot)
