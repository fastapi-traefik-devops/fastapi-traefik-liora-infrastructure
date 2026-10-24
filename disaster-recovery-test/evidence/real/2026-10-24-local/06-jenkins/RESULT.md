# Test 6 — PASS for synthetic state: actual Jenkins archive and restore

24 October 2026, approximately 10:08–10:11 Europe/Tirane.
Exact repository Jenkins base image 2.585-alpine-jdk21, pinned digest
sha256:e00aee28e0233941e1c952062b2c6f47e44447f8f5a74243dd9ac4e7d7298030.
The full custom controller/plugin image and a current original Jenkins backup
were unavailable; a real disposable controller supplied synthetic local state.

Source controller generated actual encryption files, an admin password hash,
a disabled freestyle job, and an encrypted synthetic marker. Source was stopped
before archiving. The existing, unmodified stage-jenkins-home.py validated and
prepared its 52,299,857-byte archive. It preserved both master.key and
hudson.util.Secret and rewrote controller/job configuration into held state.
A second actual controller booted from the staged archive and successfully
decrypted the retained synthetic marker. No key values or passwords appear
in public evidence. Source archive SHA-256 is in archive-receipt.json.

Source readiness: 08:08:38.498 UTC. Restored readiness: 08:09:49.972 UTC.
This interval includes observation, source shutdown and archive/staging work;
it is not a production Jenkins RTO or a precise restore-only duration.
Both API snapshots prove numExecutors=0, quietingDown=true, job buildable=false,
no builds. Three screenshots show source/restored UI and disabled job status.
The internal Docker network has no outbound gateway, no agent or Docker socket
was mounted, and no pipeline/deployment/publishing operation was executed.

This proves an actual synthetic controller-home restore using the existing
archive transformation, matching encryption material and job preservation.
It does not prove recovery of original jobs, historical builds, original
credentials, plugin configuration/compatibility, GitHub integrations or
production Jenkins state. Empty build history was verified, not invented.
Private source/staged/restored homes and backup archives are retained under
private/, excluded from public evidence and Git.
