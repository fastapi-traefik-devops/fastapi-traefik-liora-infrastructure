> Historical investigation of the retired Kubernetes Jenkins setup. The active
> Docker-only Phase 1 guide is [infra/jenkins-host/README.md](infra/jenkins-host/README.md).

# Jenkins on Kubernetes: troubleshooting cheat sheet

Investigated on 2026-10-01. Diagnose in order: context → controller → permissions → agent → build → storage.

## 1. Check where the command runs

```bash
pwd
kubectl config current-context
kubectl get namespaces
kubectl apply --dry-run=server -f k8s/rbac/jenkins-controller-dev-rbac.yaml
```

Server dry-run validates the request without saving resources. Here it returned `unchanged (server dry run)` for both resources. The original apply error was not reproduced; retain its exact text and compare the terminal's context/user.

| Error | Next check |
| --- | --- |
| File does not exist | Working directory and file path |
| Connection refused / timeout | Cluster status, API address, kubeconfig |
| Unauthorized / certificate error | Credentials and certificates |
| Forbidden | Identity named in the error and its permissions |
| Namespace not found | Target namespace and selected cluster |
| YAML/schema error | Reported field/line and manifest structure |

## 2. Separate controller health from build health

```bash
kubectl get pods,svc,statefulsets -n jenkins
kubectl logs -n jenkins jenkins-0 -c jenkins --tail=150 --timestamps
kubectl get events -n dev --sort-by=.lastTimestamp
```

Observed: `jenkins-0` was `2/2 Running`; build #29 had successfully created an agent in `dev`. A Running Pod does not prove Jenkins can save builds.

For browser access, run on the browser's machine (or use an SSH tunnel):

```bash
kubectl port-forward -n jenkins svc/jenkins 8080:8080 --address 127.0.0.1
```

Open `http://localhost:8080`; keep forwarding running.

## 3. Understand the two identities

Your kubectl identity applies RBAC. Jenkins's service account uses that RBAC to manage agent Pods. They are separate identities.

```bash
kubectl get pod jenkins-0 -n jenkins -o jsonpath='{.spec.serviceAccountName}{"\n"}'
kubectl auth can-i create pods -n dev --as=system:serviceaccount:jenkins:jenkins
kubectl auth can-i create pods/exec -n dev --as=system:serviceaccount:jenkins:jenkins
kubectl auth can-i get pods/log -n dev --as=system:serviceaccount:jenkins:jenkins
```

The controller account was `jenkins`; tested permissions returned `yes`. `--as` requires impersonation permission for your kubectl identity; an impersonation error does not prove the target account lacks access.

The Role lives in `dev`, where agents run. The RoleBinding points to account `jenkins` in namespace `jenkins`, where the controller runs. Do not grant cluster-admin to solve an unrelated build failure.

## 4. Follow the earliest concrete error

Open Jenkins → `fastapi-traefik-ci` → build #29 → Console Output. Compare with controller logs at the same time.

Confirmed on 2026-10-01 around 10:39 UTC:

```text
java.io.IOException: No space left on device
Failed to persist /var/jenkins_home/jobs/fastapi-traefik-ci/builds/29/program.dat
```

The build was extracting frontend image layers. Later agent-offline and pipeline-thread errors followed the storage failures; fix storage before investigating those as independent causes.

```bash
df -h /
df -i /
kubectl exec -n jenkins jenkins-0 -c jenkins -- df -h /var/jenkins_home
kubectl exec -n jenkins jenkins-0 -c jenkins -- df -i /var/jenkins_home
kubectl exec -n jenkins jenkins-0 -c jenkins -- du -xh --max-depth=1 /var/jenkins_home
docker system df
kubectl get pvc -n jenkins
```

`df -h` checks capacity; `df -i` checks inode availability; `du` locates usage. At inspection: root filesystem 30 GiB, 88% used, 3.7 GiB available; inodes 25% used. Jenkins home was only 234 MiB. The earlier ENOSPC is confirmed even though space was available afterward; temporary build storage being released is a plausible explanation, not a measured fact.

The Jenkins PVC requests 8 GiB but uses Minikube hostPath storage on the shared backing filesystem. Increasing the PVC number alone does not enlarge the host disk.

## 5. Recovery to perform yourself — not executed during investigation

1. Avoid starting more builds while recovering. Review host cache usage with `docker system df -v`.
2. If old host build cache is disposable, use the following interactive cleanup. It removes unused cache older than 24 hours, so later builds may need to rebuild layers:

   ```bash
   docker builder prune --filter 'until=24h'
   df -h /
   ```

   The host reported about 2.377 GB reclaimable build cache; the age filter may reclaim less. Host Docker cache and BuildKit inside a Kubernetes agent are separate stores. Avoid broad volume pruning: Minikube's active volume contains cluster data.
3. For a durable fix, back up persistent data and increase the VM disk, then expand its partition, LVM physical/logical volumes and ext4 filesystem as appropriate. Inspect `lsblk -f`, `sudo pvs`, `sudo vgs`, and `sudo lvs` first. This machine has a 32 GiB disk with a roughly 30 GiB root LV; changing a Kubernetes storage request is insufficient. Exact resize commands depend on the hypervisor and available extents.
4. Review `git diff -- Jenkinsfile`. Build #29 fetched its Jenkinsfile from Git and used a `kubectl` container absent from the current local version. Publish the reviewed intended revision and select that branch in Jenkins; local uncommitted edits are not used by an SCM pipeline.
5. Run one new build while monitoring `df -h /` and controller logs. Verify all stages finish, reports are saved, and no fresh ENOSPC appears. Do not assume the damaged build #29 can resume successfully.

## 6. Prevent recurrence

- Measure peak disk use during a full build and reserve headroom; current free space is not proof of sufficient build capacity.
- Reduce image size, manage BuildKit cache, and consider ephemeral-storage requests/limits. Limits contain consumption but do not create capacity.
- Alert on disk space/inodes. Jenkins build retention helps long-term housekeeping, but build history was not the main consumer here.
- Keep pipeline configuration in Git and verify the build's checked-out revision.

References: [kubectl dry-run](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/), [authorization checks](https://kubernetes.io/docs/reference/access-authn-authz/authorization/), [Jenkins pipeline options](https://www.jenkins.io/doc/book/pipeline/syntax/).
