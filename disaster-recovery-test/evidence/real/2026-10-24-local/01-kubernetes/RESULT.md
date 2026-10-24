# Test 1 — PASS: local Kubernetes and persistent storage

Executed 24 October 2026, approximately 09:49–09:51 Europe/Tirane.
One K3s 1.35.5 server, capped at 1536 MiB; 565.8 MiB measured after test.
Cluster kube-system UID: aa85f393-9b41-42a5-af6a-7fadfc783683.
API published only on 127.0.0.1:16443. Existing host kubeconfig was not changed.

Node Ready, API access, pod scheduling and Bound 64Mi local-path PVC verified.
Marker `liora-dr-20261024` survived a real deployment rollout to a new pod.
The storage workload was scaled to zero immediately afterward; PVC retained for rollback.
Read [verification-retry.log](verification-retry.log) for actual commands, events and exit code 0.

Failures retained: first k3d creation with --no-image-volume automatically rolled back;
first image import reported a missing multi-platform digest; stdin forwarding was corrected.
Kubelet then successfully pulled Alpine directly, as shown in events.

Limitations: this tests one disposable local node and pod replacement, not node/disk loss,
HA, Proxmox restoration, or original platform Kubernetes 1.36.5 compatibility.
