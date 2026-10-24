# Test 8 — PASS: scoped shutdown, cleanup and preservation

24 October 2026, approximately 10:15 Europe/Tirane. See cleanup.log and receipt.json.
Before shutdown the local CNPG database and operator were Ready and both lab PVCs
Bound. Node memory usage was 762.9 MiB under its 2 GiB cap.
The exact owned k3d cluster was stopped. The disposable Git-serving container's
run label was verified before removing only that container. An inspect afterward
returned expected exit code 1. No prune, shared-volume or broad-delete command ran.
The exercise's read-only Git listener was terminated after its final use.

Final docker ps was empty. The three original infra containers still exist,
are stopped by user request, and retain their volume attachments. Both original
VMs and both pre-existing k3d clusters remain stopped. Default kube context
remains k3d-gitlab-gitops. Both original repositories report clean working trees.
Final snapshot: 3.6 GiB available RAM, 2.7 GiB swap used, 200 GiB disk available.

Lab node/PVCs, stopped component containers, cached images and private synthetic
archives are retained for review/repetition; cleanup does not claim zero retained
disk use. The loopback evidence viewer is terminated after the last screenshot.
All evidence and reports remain saved. No production cluster or Proxmox endpoint
was contacted, no R2 identity imported, and no production mutation was issued.
This statement describes this run's command scope; no independent remote audit
or before/after content hash of original volumes was performed.
