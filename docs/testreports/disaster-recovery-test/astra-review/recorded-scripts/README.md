# Recorded implementation, 24 October 2026

These source snapshots document the executed one-off experiment. They retain original
workspace-relative paths, exact lab identifiers and run ordering. **Do not execute
these in place:** several overwrite output, assume existing private inputs or mutate
the disposable lab. They are not a complete automated recovery installer.
Original private files, kubeconfig, dumps, archives, vendored manifests and Git
fixture history are deliberately omitted. Re-render pinned vendor resources from
the source revision listed in the audit if reproducing in a new reviewed workspace.

Use the [guarded verifier](../scripts/verify_local_lab.py) for read-only rechecks.
Original repository DR runners and original local source files are unchanged.
The verifier improves output preservation, explicit failure handling, exact cluster
identity checking and rejection of zero-replica deployment success. It does not
claim to repair or re-execute these recorded mutating runners.
