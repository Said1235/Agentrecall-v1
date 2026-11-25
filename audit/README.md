# Audit of AgentRecall V1

Read-only security, logic and consensus audit of `contracts/agent_recall.py`.

| Item | Value |
|------|-------|
| Audited commit | `4c50da760bdd997eba9e0f6e954efae49e83f907` |
| Contract SHA-256 | `64575c671b33ebb5d9ae0972a90ab296e7dbbe1ab3b8bc0f2984d3a0914b5e9d` (unchanged by the audit) |
| Result | 0 CRITICAL, 0 HIGH, 3 MEDIUM (AR-01, AR-02, AR-03), 3 LOW, informational items |
| Limit | executed on a dev-only SDK stub; real GenVM/Studio/LLMs/consensus **not** tested |

## Documents

1. `AGENTRECALL_SECURITY_AUDIT.md` - scope, method inventory, state machine, findings, the 30 required answers
2. `AGENTRECALL_CONSENSUS_AUDIT.md` - leader/validator analysis and the answer to the key question
3. `AGENTRECALL_ADVERSARIAL_TEST_REPORT.md` - tests, exact commands, measurements, unexecuted items
4. `AGENTRECALL_REMEDIATION_PRIORITY.md` - ranked, smallest corrections (none implemented)

## Reproduce

```
python3 audit/harness/audit_harness.py -v      # 34 tests; writes audit/evidence/stats.json
python3 audit/harness/mutant_check.py          # the harness must detect injected faults
```

`audit/evidence/` holds the raw outputs referenced by the reports.
