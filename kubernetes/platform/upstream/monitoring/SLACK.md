Slack delivery uses the existing route timing and a single Slack receiver with
`send_resolved: true`. The pinned kube-prometheus-stack 92.2.0 chart mounts
`alertmanagerSpec.secrets` at `/etc/alertmanager/secrets/`; `api_url_file` reads
the `slack-webhook` key from `monitoring-slack-webhook` in namespace `monitoring`.
The incoming webhook selects its Slack channel.

The Secret is provisioned separately and already exists. Do not read or print
its value or add it to Kustomize or Git. Publish the configuration to main and
let Argo CD reconcile it.

For a controlled delivery test, use an internal loopback forward:

```sh
kubectl --context kind-fastapi-dev -n monitoring port-forward --address=127.0.0.1 svc/monitoring-alertmanager 19093:9093
```

In another terminal run `python3 monitoring/test-slack-notification.py`. Watch
the configured Slack channel for the FIRING message, then press Enter to resolve
the same alert. The script also resolves it on interruption and sets a bounded
expiry as a fallback. Allow the existing 1-minute group wait and 5-minute group
interval for delivery. Confirm both messages in Slack; API acceptance alone
does not prove channel receipt. The test adds no Prometheus rules and touches
no workloads.
