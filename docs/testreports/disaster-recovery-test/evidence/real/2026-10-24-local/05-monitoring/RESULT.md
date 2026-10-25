# Test 5 — PASS within local scope: monitoring configuration recovery

24 October 2026, approximately 10:02–10:08 Europe/Tirane.
Existing cached kube-prometheus-stack 92.2.0 chart was rendered to identify versions.
Prometheus 3.15.0 (cached standard image, same version as chart's distroless tag),
Grafana 13.2.3-distroless (exact chart tag), Alertmanager 0.34.1 (exact chart tag).

Original PrometheusRule groups from NONPROD monitoring and backup-monitoring
were converted directly to native rule files. promtool verified 15 + 15 rules.
The running Prometheus API returned loaded/evaluated rules with healthy state,
and the real self-scrape target was UP. No original Kubernetes exporters or
production targets were scraped; missing-series alerts may fire by design.

Original dashboard JSON imported with datasource UID prometheus. Grafana database
health returned ok and API listed restored dashboards. Original operations panels
show No telemetry because their source exporters are absent. An additional
clearly labeled LOCAL DR dashboard displayed actual up=1 and Prometheus process
memory metrics, never invented or copied production samples.

Prometheus measured 107.2 MiB under 384 MiB cap; Grafana 259 MiB under 512 MiB.
These components were stopped before Alertmanager's separate test (128 MiB cap).
A real synthetic alert was accepted (HTTP 200), displayed under discard receiver,
then resolved (HTTP 200); API returned zero active alerts and UI no alert groups.
All external receivers/Slack credentials were omitted. The Docker network is
internal with no outbound gateway; failed Grafana external plugin lookup is
recorded in logs. Host accessed private bridge IPs because internal-network port
publishing did not become available on localhost.

See six actual product UI screenshots, API JSON, logs, resource-usage.log and
rule-validation.log. Original TSDB/history/PVCs, Kubernetes scrape coverage,
production notification delivery and full operator/chart recovery were not tested.
