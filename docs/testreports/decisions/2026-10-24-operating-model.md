# Architecture operating-model decisions — 2026-10-24

These owner-approved decisions supersede the earlier target where it differs.
This is a documentation update; it does not apply infrastructure, credential,
Jenkins or database changes.

## Owner-reported external changes

- Cloudflare protection/Access is enabled for DEV/STAGE. PROD retains DNS-only
  access. The accepted direct-origin bypass is unchanged.
- Legacy VM100 administrative DNAT has been removed from Proxmox.

These are owner confirmations, not new independently executed network tests.
Earlier phase reports retain their original execution context; their old DNS
or NAT observations must not be used as the current operational baseline.

## Public ingress

Keep HAProxy VM 240 forwarding TLS to Traefik ServiceLB node pools:
NONPROD `.201`–`.203`, PROD `.211`–`.213`. API and Admin VIPs remain separate.
There is no dedicated ingress-VIP implementation task.

One public IPv4 is shared with host/Proxmox administration and application
DNAT. Retaining the working edge avoids an unnecessary redesign. HAProxy is
an accepted single point of failure on this single-host educational platform.
For a substantially larger production setup, optionally reassess redundant
edge ingress and additional public IP capacity. This is not a required next
phase. Private ingress VIP allocation does not itself require another public IP.

## Private Secret provisioning

Provision runtime Secrets with Ansible, reviewed helpers or a deliberate
manual procedure using private inputs under ignored `recovery/`. Git contains
only fake examples, references and provisioning logic, never live Secret
payloads, plaintext or encrypted. Maintain protected external recovery copies.
No encryption controller or controller-key rollout is part of the target.

The existing version-1 recovery checker still requires legacy key archive
records. A separately scoped schema/example update must retire that obsolete
requirement while retaining historical recovery inputs. This documentation
change does not alter the checker, examples, keys or credential values and does
not claim that schema cleanup has already been implemented.

## Adminer

Keep Adminer privately available in DEV, STAGE and PROD using the existing
Admin VIP ports and native database authentication. The owner accepts the
operational risk because this young project still needs unplanned direct
interventions. Removing PROD Adminer is not a deployment/recovery prerequisite.

Reassess possible removal in one to two years, after stable operation makes
such interventions exceptional and a usable alternative access path exists.
This is optional future improvement, not a scheduled removal commitment.

## Documentation and execution boundary

The architecture describes the resulting target; runbooks describe its
operation and recovery. Historical migration evidence and operator scripts are
preserved. Application historical journals retain their original transcripts;
they are not instructions for the current platform.

Existing uncommitted owner updates about scheduled backup output, external
certificate checks, UptimeRobot and DHCP correction were preserved. This task
neither resolves nor closes the separate backup-coordinator incident or pending
Jenkins/recovery work identified during the read-only architecture review.
