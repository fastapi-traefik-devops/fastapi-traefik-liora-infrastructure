# Configure Jenkins jobs and acceptance

**Where:** Management VM 200 for Git and Kubernetes checks; private Jenkins UI
at `http://192.168.77.16:8085` through Tailscale for job configuration.
**Inputs:** Reviewed application checkout beside the infrastructure checkout,
recovered Jenkins credentials and the selected publisher helper pin.
**Hold:** Keep Jenkins quiet, jobs disabled and polling off until section 4.

## 1. Check identities and immutable helpers

- [ ] Complete [controller setup or restoration](17-install-operate-jenkins.md#1-install-a-fresh-controller)
      and [two-worker connection](22-install-fresh-jenkins-agents.md). Confirm
      zero controller executors and an empty queue.
- [ ] In **Manage Jenkins → Credentials**, confirm folder-scoped GitHub App
      `github-ci-app` under `app-ci`; confirm `gitops-app` and username/password
      `ghcr-write` only under `trusted`. The CI App needs application Contents/PR
      read and status write. The GitOps App installation needs both repositories,
      Contents/PR write and Metadata read. Do not copy trusted credentials into
      `app-ci` or a global store.
- [ ] On VM 200, compare the pinned helper commit with the publisher manifest
      before preparing a new immutable ConfigMap. The job definition must be
      from a reviewed application revision compatible with that commit:

```sh
cd "$HOME/fastapi-traefik-liora-infrastructure"
if test ! -d ../fastapi-traefik-liora-application/.git; then
  git clone https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application.git \
    ../fastapi-traefik-liora-application
fi
git -C ../fastapi-traefik-liora-application remote get-url origin
git -C ../fastapi-traefik-liora-application fetch origin
rg 'SOURCE_COMMIT' scripts/kubernetes/prepare-jenkins-publisher-source.py
rg 'jenkins-publisher-ci-' kubernetes/platform/nonprod/jenkins/agents/workloads.yaml
mkdir -p .local-work/jenkins
bash scripts/local-python.sh scripts/kubernetes/prepare-jenkins-publisher-source.py \
  --output .local-work/jenkins/publisher-source.json
```

**Expected:** The ConfigMap name ends in the helper commit's first 12 hex
characters. The helper checks Git object hashes and records `data_sha256`.
Do not replace an existing immutable ConfigMap or repin one side alone.

## 2. Configure the three jobs while disabled

- [ ] In Jenkins, create or inspect `app-ci` as a **Multibranch Pipeline**.
      Set GitHub Branch Source to organization
      `fastapi-traefik-devops`, repository
      `fastapi-traefik-liora-application`, credential `github-ci-app`,
      branch discovery for `main`, PR discovery **merge with target**, and
      head filter `main PR-*`. Keep automatic SCM triggering suppressed for
      PR jobs. Main polling is declared by the committed `Jenkinsfile` after
      activation; do not add a competing UI poll. Keep periodic folder scans
      off until the selected policy explicitly enables them.
- [ ] Create or inspect top-level `dev-build` as a **Pipeline**. Set
      **Pipeline script from SCM**, Git URL
      `https://github.com/fastapi-traefik-devops/fastapi-traefik-liora-application.git`,
      public checkout with no credential, branch `*/main`, script path
      `Jenkinsfile.dev`, and **Lightweight checkout** enabled. Keep disabled;
      DEV runs only by operator request with a reviewed `BRANCH` parameter.
- [ ] Create folder `trusted` and its `publish` **Pipeline**. Set definition
      **Pipeline script** and paste the exact reviewed application
      `Jenkinsfile.promote` from the selected commit. Keep the job disabled;
      do not load publisher code from a candidate branch. Confirm that its
      `ACTION=stage`, `ACTION=dev` and `ACTION=prod` behavior matches the
      installed helper pin before activation. Preserve an existing job's
      history, parameters and credential scope during restoration.
- [ ] In Jenkins **Pipeline Syntax → Declarative Directive Generator / Validate**
      (or the controller's `/pipeline-model-converter/validate` endpoint),
      validate `Jenkinsfile`, `Jenkinsfile.dev` and the installed
      `Jenkinsfile.promote`. Require `Jenkinsfile successfully validated` for
      each. A successful syntax check does not authorize a build.
- [ ] For an unsandboxed trusted publisher, open **Manage Jenkins →
      In-process Script Approval**. Approve only the exact reviewed pending
      publisher script. When the application checkout `HEAD` is the reviewed
      definition and Jenkins is quiet with `trusted/publish` disabled, the
      existing bounded helper can perform the exact SHA-256 match and approval:

```sh
bash scripts/local-python.sh scripts/kubernetes/phase9-live-cycle.py approve-publisher
```

**Stop:** A different pending script, signature, helper commit, Jenkinsfile or
credential scope. Do not approve unrelated signatures or use the archived
`jobs.groovy`: it targets the old application repository and Docker bootstrap.

## 3. Connect the STAGE observer

The controller JCasC declares the `stage-observer` node. Its namespace,
read-only RBAC, NetworkPolicy and Deployment are in
[`acceptance/`](../kubernetes/platform/nonprod/jenkins/acceptance/kustomization.yaml).
The observer runs only `stage_acceptance.py` from its own immutable bundle,
pinned separately from the publisher bundle (`OBSERVER_SOURCE_COMMIT` in
[the bundle helper](../scripts/kubernetes/prepare-jenkins-publisher-source.py)).
The observer installer creates its inbound connection Secret from the held
controller; it never reads Git or a publisher token for it.

- [ ] Keep the controller quiet with all jobs disabled. Confirm that the
      generated observer bundle name matches the manifest reference:

```sh
cd "$HOME/fastapi-traefik-liora-infrastructure"
bash scripts/local-python.sh scripts/kubernetes/prepare-jenkins-publisher-source.py \
  --observer --output .local-work/jenkins/observer-source-$(date -u +%Y%m%dT%H%M%SZ).json
rg 'jenkins-acceptance-ci-' kubernetes/platform/nonprod/jenkins/acceptance/observer.yaml
```

**Expected:** `"name": "jenkins-acceptance-ci-8b584055a83c"`, the same name in
`observer.yaml`, and `data_sha256`
`d0dad33b2c91f444c6acae0299fc96489a36fd91c8675e4a1bd0687b19f911fe`.

- [ ] Connect the observer:

```sh
bash scripts/local-python.sh scripts/kubernetes/deploy-jenkins-observer.py
```

Standalone script: [deploy-jenkins-observer.py](../scripts/kubernetes/deploy-jenkins-observer.py).
It checks the execution hold and the bundle pin, validates the overlay with a
server-side dry run, installs the immutable bundle before the Deployment,
copies the registry pull Secret, creates
`jenkins-acceptance/stage-observer-connection` (key `agent-secret`) from the
controller's `stage-observer` inbound identity, deploys the observer, waits for
the node to be online and verifies the mounted helper hash. It refuses to
replace a different existing bundle or Secret. Private receipts are written
under `.local-work/private/phase9/observer-*`.

**Expected:** `deployed: true`, `controller_quiet: true`, `jobs_enabled: false`,
`observer_bundle: jenkins-acceptance-ci-8b584055a83c`. In **Manage Jenkins →
Nodes**, `stage-observer` is online with one executor.

- [ ] Acceptance is proven by the first controlled main cycle in section 4:
      the publisher commits the STAGE promotion and then an automatically
      produced `overlays/stage/acceptance.json` with `"status": "accepted"`
      for the exact application SHA and frontend/backend digest pair.

**If interrupted:** Keep jobs disabled. Inspect the latest receipt and the
observer Pod events, then rerun the same command; a matching bundle and Secret
are reused.

## 4. Release only the approved policy

- [ ] Record the current job enabled states, triggers, quiet mode and queue.
      Activate only the agreed jobs and schedules. Test one controlled main
      cycle and require automatic STAGE acceptance before considering PROD.
      Follow [runbook 17, section 4](17-install-operate-jenkins.md#4-activate-delivery).
- [ ] PROD has no job to enable: releases run on demand in `trusted/publish`
      with `ACTION=prod`, `APP_SHA` and `RELEASE_TAG` (see
      [CI/CD, PROD release](../docs/CI_CD.md#prod-release-and-rollback)).
      Confirm the three parameters are visible after installing
      `Jenkinsfile.promote`.
- [ ] On a restored controller, restore the *recorded* job allowlist and
      trigger state, not generic defaults. On restart, check those settings
      before selecting **Cancel Shutdown**.

**If interrupted:** Leave quiet mode on and jobs disabled. Compare the
installed job definition, immutable ConfigMap name and current queue with
the recorded state before continuing. Do not request a second publication
for an unknown candidate.
