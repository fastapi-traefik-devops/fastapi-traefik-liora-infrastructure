# Hold surviving automation during disaster recovery

**Where:** A surviving administrator host with access to the existing
clusters. Use its existing kubeconfigs. Do not run these commands against
replacement clusters.

## Check the target

- [ ] If no old cluster is reachable, record that fact in the incident log.
      Continue with the recovery checklist. Do not create an old-cluster
      kubeconfig from the new cluster.
- [ ] If a cluster is reachable, check its API address, nodes, and Argo
      Applications before changing a sync policy:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" config view --minify -o jsonpath='{.clusters[0].cluster.server}'
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n argocd get applications
kubectl --kubeconfig="$HOME/.kube/config-prod" config view --minify -o jsonpath='{.clusters[0].cluster.server}'
kubectl --kubeconfig="$HOME/.kube/config-prod" -n argocd get applications
```

The old NONPROD cluster uses API VIP `192.168.77.11`; PROD uses
`192.168.77.12`. If either identity differs, do not patch it.

## Hold Argo CD

- [ ] On each reachable old cluster, remove automatic sync from the root
      Application first, then its application children. Run only the commands
      for that reachable cluster:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n argocd patch application liora-root-nonprod --type=merge -p '{"spec":{"syncPolicy":{"automated":null}}}'
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n argocd patch application app-dev --type=merge -p '{"spec":{"syncPolicy":{"automated":null}}}'
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n argocd patch application app-stage --type=merge -p '{"spec":{"syncPolicy":{"automated":null}}}'
```

```sh
kubectl --kubeconfig="$HOME/.kube/config-prod" -n argocd patch application liora-root-prod --type=merge -p '{"spec":{"syncPolicy":{"automated":null}}}'
kubectl --kubeconfig="$HOME/.kube/config-prod" -n argocd patch application app-prod --type=merge -p '{"spec":{"syncPolicy":{"automated":null}}}'
```

- [ ] Read back the Applications. Confirm `spec.syncPolicy.automated`
      is absent on every patched Application:

```sh
kubectl --kubeconfig="$HOME/.kube/config-dev-stage" -n argocd get applications -o jsonpath='{range .items[*]}{.metadata.name}{" automated="}{.spec.syncPolicy.automated}{"\n"}{end}'
kubectl --kubeconfig="$HOME/.kube/config-prod" -n argocd get applications -o jsonpath='{range .items[*]}{.metadata.name}{" automated="}{.spec.syncPolicy.automated}{"\n"}{end}'
```

## Hold Jenkins

- [ ] If the old Jenkins UI is reachable through Tailscale, use
      **Manage Jenkins → Prepare for Shutdown**. Wait for running builds
      to finish. Record queued jobs. If the UI is unreachable, record that
      status in the incident log.

**Done when:** Reachable old Applications have no automatic sync, Jenkins
accepts no new builds, and unreachable components are recorded.
