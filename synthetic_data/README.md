Synthetic pipeline-run generator for the AI Data Engineering Copilot.

Each RUN_xxxxxx folder contains:
- metadata.json: structured metadata consumed by DbMeta
- execution.log: execution timeline
- error.log: failure-specific evidence
- audit.json: auxiliary event information

The metadata and logs are generated from the same scenario so they remain correlated.
