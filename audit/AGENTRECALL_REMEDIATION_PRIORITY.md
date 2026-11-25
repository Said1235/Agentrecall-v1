# AgentRecall V1 - Remediation priority

Nothing below was implemented. The contract at commit `4c50da760bdd997eba9e0f6e954efae49e83f907` is unchanged. Each item names the **smallest safe correction direction** and the regression test that must accompany it.

No CRITICAL or HIGH finding is confirmed.

## Ranking

| Rank | ID | Severity | Status | Why this rank |
|------|----|----------|--------|---------------|
| 1 | AR-12 + AR-11 | gate | MISSING COVERAGE / UNVERIFIED | Every conclusion in this audit comes from a stub. The first delivery of this contract passed its own tests and still could not be deployed. Real tooling is the highest-value next step. |
| 2 | AR-01 | MEDIUM | CONFIRMED, owner decision | The only confirmed behaviour that can produce a result the requester did not ask for. |
| 3 | AR-03 | MEDIUM (impact unverified) | CONFIRMED measurement | Cheap to bound deterministically; feeds AR-02. |
| 4 | AR-02 | MEDIUM | CONFIRMED structure, owner decision | Permanent `CHALLENGED` needs an explicit product answer. |
| 5 | AR-05 | LOW | DOC DISCREPANCY | Correct the figures after AR-03 is decided. |
| 6 | AR-04 | LOW | CONFIRMED | Hardening; no integrity impact. |
| 7 | AR-10 | INFO | frontend gaps | Decide before the DApp is built. |
| 8 | AR-14 | LOW | UNVERIFIED | Only matters if the SDK Keccak is unavailable. |
| 9 | AR-06 / AR-07 | INFO | design limitations | Accept and communicate; cannot be removed by code. |
| - | AR-08 / AR-09 / AR-13 | INFO | no action required | Not vulnerabilities. |

## Items

### 1. AR-12 / AR-11 - Run the real toolchain (before anything else)
- **Smallest action:** on the Studio you are authorised to use (v0.123, GenVM v0.4): deploy `contracts/smoke_test.py`, then `contracts/agent_recall.py`; run `genvm-lint check` and `genvm-lint schema`; execute `tests/direct/` with `direct_vm.check_pickling = True` and `genlayer-test` 0.30.0; execute `tests/integration/` with fees attached; add Studio tests with mocked validators for the 15 rejection scenarios; run at least one real adjudication per outcome and record `UNDETERMINED` behaviour.
- **Regression test:** the existing files; report every failure with the exact receipt text.

### 2. AR-01 - Undisputed criteria are adjudicated
- **Decision needed from the owner:** keep decision E12 (every criterion is re-evaluated) or follow the binding spec (adjudicate the disputed criteria).
- **If the spec governs - smallest change:** build `ctx["criteria"]` (lines 1010-1021) from the committed criteria whose ids are in `disputed`, and require/derive `overall_outcome` over that subset; keep storing the full commitment. No new state, no new methods.
- **If E12 stays:** no code change; the frontend must state that every criterion is re-evaluated and that a challenge on one criterion can change the others; keep `docs/DECISIONS.md` E12 as the authority.
- **Regression test:** challenge `C1` of `{C1,C2,C3}`; the result contains exactly the chosen set (or, under E12, the UI/doc text is asserted).

### 3. AR-03 - Escaped prompt size
- **Smallest change:** compute `len(_data_block(ctx))` (line 584) before the nondeterministic block and reject above a fixed bound with a deterministic `[EXPECTED] INPUT_TOO_LARGE`; alternatively lower the byte limits (lines 95-111) so that the worst case (4-byte characters, x2.81 observed) stays under the bound the target LLM providers are known to accept.
- **Also:** measure real providers' behaviour at the chosen bound, including whether any provider silently truncates.
- **Regression test:** maximum astral-character input is rejected deterministically (or fits under the bound) and never reaches the LLM.

### 4. AR-02 - `CHALLENGED` has no exit
- **Owner decision:** either document that an unadjudicable challenge is a known operational state, or add one explicit transition (for example a requester-only withdrawal from `CHALLENGED` to `UNCONTESTED`, which records no verdict). The second option is a new lifecycle transition and therefore a product change that this audit does not recommend implementing without approval.
- **Regression test:** the chosen exit leaves no adjudication record and cannot be called by the executor or a relayer.

### 5. AR-05 - Documentation figures
- **Smallest change:** replace "~37 KB" in `docs/DEPLOYMENT_READINESS.md`, `docs/SECURITY_AUDIT.md` and (via `tools/gen_test_report.py`) `docs/TEST_REPORT.md` with the measured 40.4 KB (ASCII) / 113.8 KB (astral) or the new bound from item 3.

### 6. AR-04 - Duplicate JSON keys
- **Smallest change:** parse with `json.loads(text, object_pairs_hook=...)` that raises on duplicate keys (standard library, line 198-219).
- **Regression test:** `[{"id":"E1","id":"E2",...}]` -> `[EXPECTED] INVALID_JSON`.

### 7. AR-10 - Frontend gaps
- **Decide before building the DApp:** how executors discover commitments addressed to them (off-chain notification, or an on-chain mechanism the owner approves); keep reading state through views; add a fee-aware deploy/test configuration (Studio v0.123 requires fees on every deploy and write).

### 8. AR-14 - Keccak fallback cost
- **Verify** that the SDK `Keccak256` import works on the real runner (then the fallback is dead code); if it is not available, measure the pure-Python cost inside GenVM at the maximum hashed volume.

## Release gate suggested for DApp integration

1. Items 1-4 resolved or explicitly accepted by the owner.
2. Real-tool results recorded in `docs/TEST_REPORT.md`.
3. AR-05 corrected.
