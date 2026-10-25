# Connect Jenkins agents

**Where:** Management VM 200, `$HOME/fastapi-traefik-liora-infrastructure`.
**Target:** NONPROD only; `http://192.168.77.16:8085` through Tailscale.
**Effect:** Restarts the controller with the same home and image. Connects
`host-ci` and `registry-publisher`. Does not run builds.

## 1. Check prerequisites

- [ ] Install a fresh controller with [runbook 17, section 1](17-install-operate-jenkins.md#1-install-a-fresh-controller), or restore its home with [runbook 23](23-restore-jenkins-controller.md).
- [ ] Open Jenkins. Confirm the administrator login works.
- [ ] Disable every job. In each job, select **Disable Project**; for multibranch projects, also remove periodic folder scanning under **Configure**.
- [ ] Select **Manage Jenkins → Prepare for Shutdown**. Let running builds finish. Cancel queued requests after recording them.
- [ ] Confirm zero controller executors under **Manage Jenkins → System**.
- [ ] Confirm the private `jenkins-foundation-login` Secret contains the password of the restored `admin` account. If necessary, restore its matching value with [runbook 23, section 5](23-restore-jenkins-controller.md#5-reconnect-or-roll-back); do not reset the account to match the Secret.
- [ ] Check the target and storage:

```sh
cd "$HOME/fastapi-traefik-liora-infrastructure"
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" get nodes
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins get deployment/jenkins,pvc
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins get deployment/jenkins -o jsonpath='{range .spec.template.spec.volumes[*]}{.name}{" "}{.persistentVolumeClaim.claimName}{"\n"}{end}'
```

**Expected:** All nodes Ready; one ready controller; its selected home PVC Bound.
**Stop:** Wrong cluster, unknown home, running/queued work, enabled jobs, or missing private login/pull credentials.

## 2. Check pinned inputs

- [ ] Keep the application checkout beside this checkout. Fetch the reviewed helper revision without changing its working tree:

```sh
git -C ../fastapi-traefik-liora-application fetch origin
bash scripts/local-python.sh scripts/kubernetes/prepare-jenkins-publisher-source.py --help
kubectl kustomize kubernetes/platform/nonprod/jenkins/agents > /dev/null
```

- [ ] Review the pinned source revision in [the bundle helper](../scripts/kubernetes/prepare-jenkins-publisher-source.py) and worker image digests in [workloads.yaml](../kubernetes/platform/nonprod/jenkins/agents/workloads.yaml).
- [ ] Confirm the publisher job definition is compatible with that helper revision before later activation. Do not repin helpers as part of agent connection.

**Stop:** Missing pinned Git object, unreviewed image/helper change, or job/helper mismatch.
Do not apply `agents/` or `initial-cycle/` directly to a fresh home: these
static overlays select the restored-home PVC. The helper below preserves the
controller's actual home instead.

## 3. Connect the two workers

- [ ] Run the installer:

```sh
bash scripts/local-python.sh scripts/kubernetes/deploy-jenkins-agents.py
```

Standalone script: [deploy-jenkins-agents.py](../scripts/kubernetes/deploy-jenkins-agents.py).

The installer checks the execution hold, preserves the selected controller PVC
and image, configures inbound nodes, installs a startup quiet-mode hook, copies
the existing registry pull Secret, and creates inbound connection Secrets.
It refuses to replace a different existing Secret. It installs the pinned
publisher bundle without executing it. Private receipts are written under
`.local-work/private/phase9/agents-*`; protect them as operator data.

**Expected:** `deployed: true`, `controller_quiet: true`, `jobs_enabled: false`,
`publication_enabled: false`.

**If interrupted:** Keep jobs disabled. Inspect the latest receipt directory
and Pod events. Resolve the reported failure before rerunning the same command.
Matching connection Secrets are reused. A different Secret requires an explicit
identity review; do not delete it to bypass the check.

## 4. Verify connections

- [ ] Check worker readiness:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins-ci rollout status deployment/host-ci --timeout=15m
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n jenkins-publisher rollout status deployment/registry-publisher --timeout=15m
```

- [ ] Open **Manage Jenkins → Nodes**. Confirm `host-ci` and `registry-publisher` are online, each with one executor, its matching label and remote root `/home/jenkins/agent`.
- [ ] Confirm the controller remains in quiet mode, all jobs are disabled, and the queue is empty.
- [ ] If a Pod is Ready but the node is offline, inspect that namespace's Pod events and agent container logs. Check the inbound identity and controller URL. Do not launch a build to test the connection.
- [ ] Treat `stage-observer` separately from these two workers. Follow
      [the acceptance gate](27-configure-jenkins-jobs.md#3-prepare-the-stage-observer-separately)
      before enabling automatic acceptance. Its node declaration alone does
      not install the workload.

**Done when:** Both workers are online; administrator login and controller home
are unchanged; no build, publication or deployment has run.

For job configuration and approved activation, continue with
[runbook 17, sections 2–4](17-install-operate-jenkins.md#2-configure-delivery-identities).
Agent connection alone does not authorize enabling polling or promotion.
