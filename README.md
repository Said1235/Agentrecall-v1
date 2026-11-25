# AgentRecall V1

A GenLayer **Intelligent Contract** that records bilateral commitments between two participants
(a *requester* and an *executor*) and, when the requester disputes a delivery, adjudicates each
acceptance criterion through GenLayer validator consensus. The only consequence is an immutable,
independently retrievable adjudication record: no payments, tokens, escrow, reputation or
penalties.

> **Status: implemented, partially verified.** The first delivery could **not** be deployed
> ("Could not load contract schema"): its header put comment lines directly under the runner line, and
> GenVM reads that whole block as the runner JSON (`invalid_contract runner malformed`). That is fixed and
> regression-tested; see `docs/DEPLOYMENT_READINESS.md`. Logic is tested (94 harness tests, 19/19
> mutations detected) against a hand-written SDK stub. The linter, the official Direct Mode tests,
> Studio integration tests and real consensus have **not** been run, and the real deployment has not been
> re-attempted by the author. Nothing is deployed. See `docs/TEST_REPORT.md`.

## How it works

```
OPEN -> ACCEPTED -> SUBMITTED -> CHALLENGED -> ADJUDICATED
  \-> REJECTED       \-> UNCONTESTED (explicit requester action; not a verdict)
  \-> CANCELLED (requester, only while OPEN)
```

- Criteria are immutable and individually evaluated as `MET`, `NOT_MET` or `INDETERMINATE`
  with fixed reason codes and references to committed evidence. The overall outcome is derived.
- Only hashes of delivered material are stored. Adjudication (callable by anyone) requires the
  original material to be sent again and verifies it by hash before any LLM runs.
- Consensus: the leader proposes a closed-vocabulary result with no free text. Each validator
  re-checks it deterministically, evaluates every criterion independently, requires identical
  per-criterion outcomes, and runs a second check that the cited evidence supports the claims.
  Technical failures never persist a verdict.
- Evidence is only what participants submit. URLs are never fetched, code is never executed,
  and validator agreement is not proof of truth.

## Repository layout

```
contracts/agent_recall.py          the contract (single file, GenVM v0.4, runner py-genlayer:kzybg95x...)
contracts/smoke_test.py            40-line deployment smoke test (same header/imports/storage); deploy it first to bisect
tests/direct/                      Direct Mode tests (pytest + genlayer-test)  - not executed
tests/integration/                 Local Studio tests (gltest)                 - not executed
tests/harness/                     runnable logic harness + stub SDK (dev only)
tools/                             mutation check and test-report generator
docs/                              research, requirements, architecture, consensus, state machine,
                                   threat model, decisions, test report, security audit,
                                   frontend integration, deployment readiness
```

## Quick start

```
python3 -m unittest discover -s tests/harness -v      # runs anywhere, no dependencies
python3 tools/mutation_check.py                       # proves the tests catch injected defects
```

With the GenLayer toolchain installed (genlayer-test 0.30.0, CLI 0.40.0 - the versions for Studio v0.123):

```
genvm-lint check contracts/agent_recall.py --json
pytest tests/direct/ -v
gltest tests/integration/ -v -s                         # fees apply on Studio v0.123
```

## Independent audit

`audit/` contains a read-only security, logic and consensus audit of the contract at commit
`4c50da7` (0 CRITICAL, 0 HIGH, 3 MEDIUM, 3 LOW). Start with `audit/README.md`. The audit ran on a
dev-only SDK stub: real GenVM, Studio, LLMs and consensus were **not** tested.

## Where to look

| If you are... | Read |
|---------------|------|
| A frontend engineer | `docs/FRONTEND_INTEGRATION.md` |
| Reviewing security or consensus | `audit/AGENTRECALL_SECURITY_AUDIT.md`, `audit/AGENTRECALL_CONSENSUS_AUDIT.md`, then `docs/CONSENSUS_DESIGN.md`, `docs/THREAT_MODEL.md` |
| Checking what was actually verified | `docs/TEST_REPORT.md`, `docs/RESEARCH.md` |
| Deploying | `docs/DEPLOYMENT_READINESS.md` (no public deployment is authorized) |
| Wondering why something is the way it is | `docs/DECISIONS.md` |

## Open items

1. Run the linter, Direct Mode tests and local Studio tests; fix whatever the real toolchain reports.
2. Owner decisions from the audit: AR-01 (all criteria evaluated vs only disputed ones, `docs/DECISIONS.md` E12), AR-02 (no exit from `CHALLENGED`), AR-03 (prompt size up to ~114 KB). See `audit/AGENTRECALL_REMEDIATION_PRIORITY.md`.
3. Deploy on the Studio (paste the file unchanged, first line `# v0.4.0`) and report the exact receipt text if it still fails; the unverified runtime behaviours are listed in `docs/DEPLOYMENT_READINESS.md`.
