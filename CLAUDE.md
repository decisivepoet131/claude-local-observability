# Claude Local Observability

This project sets up a local observability stack for Claude Code telemetry.

## Stack
- **OTel Collector** — receives OTLP from Claude Code on :4317 (gRPC) / :4318 (HTTP)
- **Prometheus** — scrapes metrics from OTel Collector :8889
- **Loki** — receives logs from OTel Collector
- **Grafana** — dashboards at http://localhost:3000 (admin/admin)

## Rules
- Before making any claims about Claude Code telemetry settings, env vars, or features, always verify against the official Claude Code documentation using the claude-code-guide agent. Do not rely on general knowledge.
