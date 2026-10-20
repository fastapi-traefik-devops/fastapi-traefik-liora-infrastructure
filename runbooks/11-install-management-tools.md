# Install Ansible and Terraform on VM 200

**Where:** Management VM 200, Debian 13.

Terraform is the default command in the remaining runbooks. Install Terraform or OpenTofu; use `tofu` in place of `terraform` throughout if choosing OpenTofu.

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

**Done when:** `ansible --version` and either `terraform version` or `tofu version` succeed on VM 200.
