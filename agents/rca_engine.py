class RCAEngine:
    """
    Deterministic evidence correlator.

    This is deliberately separate from the LLM. It produces evidence that
    a future LangGraph RCA agent can consume and explain.
    """

    def analyze(self, metadata, logs):
        scenario = metadata.get("execution", {}).get("failure_reason")
        evidence = []
        root_cause = scenario

        if scenario == "DATA_SKEW":
            resources = metadata.get("resources", {})
            evidence.extend([
                f"shuffle_read_gb={resources.get('shuffle_read_gb')}",
                f"shuffle_write_gb={resources.get('shuffle_write_gb')}",
                f"peak_memory_gb={resources.get('peak_memory_gb')}",
            ])

        elif scenario == "OUT_OF_MEMORY":
            resources = metadata.get("resources", {})
            evidence.extend([
                f"executor_memory_gb={resources.get('executor_memory_gb')}",
                f"peak_memory_gb={resources.get('peak_memory_gb')}",
            ])

        elif scenario == "SCHEMA_MISMATCH":
            evidence.append(
                f"schema_valid={metadata.get('data_quality', {}).get('schema_valid')}"
            )

        elif scenario == "PARTITION_MISSING":
            inp = metadata.get("input", {})
            evidence.extend([
                f"files_expected={inp.get('files_expected')}",
                f"files_read={inp.get('files_read')}",
                f"rows_in={inp.get('rows_in')}",
            ])

        elif scenario == "DUPLICATE_DATA":
            evidence.append(
                f"duplicate_rate_pct={metadata.get('data_quality', {}).get('duplicate_rate_pct')}"
            )

        elif scenario == "NULL_SPIKE":
            evidence.append(
                f"null_rate_pct={metadata.get('data_quality', {}).get('null_rate_pct')}"
            )

        return {
            "root_cause": root_cause,
            "evidence": evidence,
            "log_evidence": logs.strip().splitlines()[-5:],
        }
