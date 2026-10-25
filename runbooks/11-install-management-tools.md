# Install management and operator tools

**Where:** Management VM 200, Debian 13, infrastructure repository root.

Install Terraform by default. If you select OpenTofu, use `tofu` in place
of `terraform` in all later commands.

## Ansible

- [ ] Install Ansible and check its version:

```sh
sudo apt-get install ansible
ansible --version
```

## Terraform (default)

Install the tools required by the HashiCorp APT repository, then install Terraform.

> [!IMPORTANT]
> If an earlier step set `umask 077`, restore `umask 022` before installing APT packages. The command block does this first.

- [ ] Install Terraform and check its version:

```sh
umask 022
sudo apt-get update
sudo apt-get install -y wget gnupg lsb-release ca-certificates curl
wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg > /dev/null
gpg --no-default-keyring --keyring /usr/share/keyrings/hashicorp-archive-keyring.gpg --fingerprint
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update
sudo apt-get install terraform
terraform version
```

Compare the displayed signing-key fingerprint with the [official HashiCorp installation instructions](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli) before trusting the new repository.

## OpenTofu (alternative)

- [ ] Install OpenTofu and check its version if you chose it instead of Terraform. Inspect the downloaded installer before running it:

```sh
sudo apt-get update
sudo apt-get install -y curl ca-certificates
curl --proto '=https' --tlsv1.2 -fsSL https://get.opentofu.org/install-opentofu.sh -o install-opentofu.sh
# Inspect the downloaded script before running it.
cat install-opentofu.sh
chmod +x install-opentofu.sh
./install-opentofu.sh --install-method deb
rm -f install-opentofu.sh
tofu version
```

The installer method follows the [official OpenTofu Debian instructions](https://opentofu.org/docs/intro/install/deb/).

## kubectl

The inventories pin K3s `v1.36.5+k3s1`; use the matching Kubernetes client
minor version. Recheck both inventory pins before changing this version.

- [ ] Download the client and its checksum, verify them, and install the
      client on VM 200:

```sh
(
set -e
umask 077
kubectl_version=v1.36.5
kubectl_arch="$(dpkg --print-architecture)"
case "$kubectl_arch" in amd64|arm64) ;; *) echo 'Unsupported architecture' >&2; exit 1 ;; esac
mkdir -p .local-work/tools
curl -fL "https://dl.k8s.io/release/$kubectl_version/bin/linux/$kubectl_arch/kubectl" -o .local-work/tools/kubectl
curl -fL "https://dl.k8s.io/release/$kubectl_version/bin/linux/$kubectl_arch/kubectl.sha256" -o .local-work/tools/kubectl.sha256
(cd .local-work/tools && echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check)
sudo install -o root -g root -m 0755 .local-work/tools/kubectl /usr/local/bin/kubectl
kubectl version --client
)
```

The download and checksum method follows the [official Kubernetes Linux installation guide](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/).

## kubeconform

- [ ] Install kubeconform for strict GitOps manifest validation. The existing
      helper downloads checksum-verified Linux amd64 binaries of kubeconform and
      kustomize using [the repository tool lock](../scripts/ci/tools.lock.json):

```sh
(
set -e
python3 scripts/ci/install-validation-tools.py .local-work/tools/validation
sudo install -o root -g root -m 0755 .local-work/tools/validation/kubeconform /usr/local/bin/kubeconform
kubeconform -v
)
```

Run from the infrastructure repository root on VM 200. The helper also leaves
kustomize in `.local-work/tools/validation`; the validator can use the installed
kubectl to render manifests. See [GitOps validation](../scripts/ci/README.md) for
strict validation commands and schema updates.

## Helm

- [ ] Install Helm from its Debian APT repository and check the version. Verify
      the signing-key fingerprint before adding the repository:

```sh
(
set -e
umask 022
sudo apt-get update
sudo apt-get install -y curl gpg
curl -fsSL https://packages.buildkite.com/helm-linux/helm-debian/gpgkey -o /tmp/liora-helm.asc
helm_key_fingerprint="$(gpg --import --import-options=show-only --with-colons /tmp/liora-helm.asc | awk -F: '$1 == "fpr" {print $10}' | head -n 1)"
test "$helm_key_fingerprint" = DDF78C3E6EBB2D2CC223C95C62BA89D07698DBC6
sudo install -m 0644 -Dt /etc/apt/keyrings/ /tmp/liora-helm.asc
printf 'Types: deb\nURIs: https://packages.buildkite.com/helm-linux/helm-debian/any/\nSuites: any\nComponents: main\nSigned-By: /etc/apt/keyrings/liora-helm.asc\n' |
  sudo tee /etc/apt/sources.list.d/liora-helm.sources > /dev/null
sudo apt-get update
sudo apt-get install -y helm
helm version
)
```

The repository and fingerprint follow the [official Helm Debian installation guide](https://helm.sh/docs/intro/install/).

## Operator Python and browser tools

- [ ] Work from the infrastructure repository root on the operator machine.
- [ ] Install Python 3 with venv support; verify that the interpreter meets the pinned requirements before creating the environment.
- [ ] Check [private operator data](../recovery/README.md#private-operator-data) before reusing or cleaning `.local-work/`.
- [ ] Create the checkout-local environment and install pinned dependencies:

```sh
umask 077
mkdir -p .local-work
chmod 700 .local-work
python3 -m venv .local-work/venv
.local-work/venv/bin/python -m pip install -r scripts/requirements-local-tools.txt
.local-work/venv/bin/python -m pip install --require-hashes -r scripts/backups/requirements.txt
.local-work/venv/bin/python -m pip check
bash scripts/local-python.sh -m playwright install --with-deps chromium
```

Pinned requirements: [operator/browser tools](../scripts/requirements-local-tools.txt),
[backup tools](../scripts/backups/requirements.txt).

Chromium system-library installation requires package-management privileges.
The wrapper sets the browser download path to `.local-work/browsers/` and can
load extracted libraries from `.local-work/browser-deps/root/`. Install native
dependencies for the current machine; do not copy virtual environments between
machines or relocate them as a provisioning step.

- [ ] Use the wrapper for operator scripts and dependency checks:

```sh
bash scripts/local-python.sh -c 'import yaml, boto3; from playwright.sync_api import sync_playwright'
RECOVERY_PYTHON="$PWD/.local-work/venv/bin/python" bash recovery/check_credentials.sh --all --offline
```

Standalone launcher: [local-python.sh](../scripts/local-python.sh).
The wrapper accepts a script path followed by its normal arguments. Follow the
selected runbook for environment variables and authorization before invoking a
script that creates resources or performs application writes.

### Additional validation binaries

- [ ] Install any additional validation binaries required by the selected procedure using its pinned source/version/checksum records.
- [ ] Keep local binaries under `.local-work/tools/` or another operator-owned path and pass their explicit paths to validators.
- [ ] Install Gitleaks separately when a credential scan is required; it is not a Python dependency. Target source paths, enable redaction and exclude private operator data.
- [ ] Recreate disposable tools/cache from their pins; preserve required private data through the recovery kit procedure.

**Done when:** Ansible, Terraform/OpenTofu, kubectl, kubeconform and Helm report versions;
the Python dependency check succeeds, Chromium dependencies are installed, and
the wrapper imports the required operator packages.
