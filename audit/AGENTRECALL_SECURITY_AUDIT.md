# AgentRecall V1 - Security, logic and consensus audit

Read-only assessment of the existing implementation. The contract was **not** modified.

## 0. Executive summary

| | |
|--|--|
| Verdict | **No CRITICAL or HIGH defect was found in the contract's logic.** Three MEDIUM findings need an owner decision or a bounded fix before DApp integration (AR-01, AR-02, AR-03). Several core properties **cannot be verified in this environment** (see section 18). |
| Most important question | *Can AgentRecall accept and persist an adjudication that materially contradicts the commitment, criteria, deliverable, challenge or evidence because its validator fails to independently verify the complete decision-critical result?* **No, not through a structural or decision-field weakness.** 12,303 mutations of a leader proposal produced **0** accepted proposals with a different overall outcome, criterion set, per-criterion outcome, id or hash. The remaining exposure is LLM-judgement quality and the points in AR-01/AR-03, which code cannot remove and this audit could not test with real LLMs. Details: `AGENTRECALL_CONSENSUS_AUDIT.md` section 9. |
| What is not tested | Real GenVM, real storage, real LLMs, real validators, `genvm-lint`, official Direct Mode, Studio. Everything below marked "executed" ran against a dev-only SDK **stub** in plain CPython. |

## 1. Identity of the audited artifact

| Item | Value |
|------|-------|
| Repository | `agentrecall` (local git repository created for this packaging) |
| Branch | `main` |
| **Audited commit** | `4c50da760bdd997eba9e0f6e954efae49e83f907` |
| `git status --short` before audit | empty (clean tree) |
| `git status --short` after audit | empty for tracked files; the audit added only the untracked `audit/` directory |
| Contract | `contracts/agent_recall.py`, 1198 lines, SHA-256 `64575c671b33ebb5d9ae0972a90ab296e7dbbe1ab3b8bc0f2984d3a0914b5e9d` (re-verified unchanged at the end) |
| Python | 3.12.3 |
| Installed GenLayer tooling | **none** (`genvm-lint`, `genlayer` CLI, `gltest`, `pytest`, Docker, network for the shell: all unavailable). Only `cloudpickle 3.1.2` is installed. Raw output: `evidence/00_environment.txt` |
| Runner (line 2) | `py-genlayer:kzybg95x1gn21dw72m7hyg0maaap04n4nx55j9yt6fkdqxtz6bz0` (the v0.4 runner named by the official Studio v0.123 announcement and the audit prompt) |

## 2. Scope and method

1. Source reading of the whole contract with line numbers (this document cites them).
2. Existing tests re-run unchanged (94 tests, 19 mutations): `evidence/01_*`, `evidence/02_*`.
3. A **new, independent adversarial harness** (`audit/harness/audit_harness.py`, 34 tests) built outside the tracked source, then added to `audit/` after the audit. It does not reuse the author's tests. It contains: type-confusion fuzzing with before/after state comparison, a model-based random walk against an independent reference model, mutation fuzzing of the leader proposal with an independent structural oracle, byte-exactness and cross-record substitution tests, authorization matrices, replay and terminal-state tests, AST-based storage/closure/determinism checks, resource measurements, and a static v0.4 compatibility checklist.
4. A **meta-check** that the harness detects defects: it was run against 16 deliberately broken copies of the contract; 15 are detected, 1 survivor is an equivalent mutant (AR-09). `evidence/04_*`.
5. Official documentation (section 3).

Severity scale and finding categories are those of the audit prompt. Test references such as `A5_actor_by_operation_matrix` mean test class `A5_...` in `audit/harness/audit_harness.py`, method `test_actor_by_operation_matrix`; the full mapping is in `AGENTRECALL_ADVERSARIAL_TEST_REPORT.md`.

## 3. Official references

| Reference | Read? | Used for |
|-----------|-------|----------|
| SDK API reference (`api.txt`) | partially (fetch truncated; changelog, runners, `genlayer.vm`, `nondet`, `message`, `types` read; later sections not) | API names, `run_nondet_default`, `Result`, `Return`, runner hash |
| GenVM v0.4 migration guide | yes | compatibility checklist (section 13) |
| Non-determinism page | yes | nondeterministic blocks and storage rules |
| Error-handling page | yes (older API naming) | error classes, leader-error handling |
| Prompt-injection page | yes | strategies: restrict inputs/outputs, simple logic, human review |
| Storage page | yes (older API naming) | storage types |
| Transaction statuses / execution | yes | consensus outcomes, appeals |
| genlayer-docs issue #487 | yes | runner-header parsing |
| Studio v0.123 announcements (supplied) | yes | fees, versions, chain IDs |
| Equivalence Principle, Calling LLMs, Testing, full-documentation, frontend/fee pages, skills site, boilerplate source (blocked by robots.txt) | **no** | conclusions that would depend on them are marked UNVERIFIED |

Documentation conflict rule applied: the SDK reference and migration guide take precedence over older conceptual pages (which still show `run_nondet_unsafe`, `.message`, `allow_storage`).

## 4. Functional model - public method inventory

Source lines refer to `contracts/agent_recall.py`. All writes are plain transactions; only `adjudicate` runs non-deterministic execution. Replay column: every write is one-time because a state or existence check follows authorization.

| Method (lines) | Access | Authorized caller | Required state | Inputs (all `str`) | State mutation | Nondet | Failure paths | Output |
|----------------|--------|-------------------|----------------|--------------------|----------------|--------|---------------|--------|
| `create_commitment` (822-860) | write | anyone -> becomes requester | none | nonce, executor (hex), description, criteria_json, accepted_evidence_kinds_json | `commitments[cid]`, `commitment_status[cid]=OPEN` | no | INVALID_INPUT, INVALID_JSON, INPUT_TOO_LARGE, DUPLICATE_ID, ALREADY_EXISTS | commitment id |
| `accept_commitment` (863-868) | write | executor | OPEN | commitment_id | status -> ACCEPTED | no | NOT_FOUND, UNAUTHORIZED, INVALID_STATE | - |
| `reject_commitment` (871-876) | write | executor | OPEN | commitment_id | status -> REJECTED | no | same | - |
| `cancel_commitment` (879-884) | write | requester | OPEN | commitment_id | status -> CANCELLED | no | same | - |
| `submit_delivery` (887-914) | write | executor | ACCEPTED | commitment_id, content, evidence_json | `submissions[sid]`, status -> SUBMITTED | no | + INVALID_INPUT, INVALID_JSON, INPUT_TOO_LARGE, DUPLICATE_ID, DUPLICATE_EVIDENCE | submission id |
| `create_challenge` (917-956) | write | requester | SUBMITTED | commitment_id, statement, disputed_ids_json, challenge_evidence_json | `challenges[chid]`, status -> CHALLENGED | no | + UNKNOWN_CRITERION | challenge id |
| `close_uncontested` (959-965) | write | requester | SUBMITTED | commitment_id | status -> UNCONTESTED | no | NOT_FOUND, UNAUTHORIZED, INVALID_STATE | - |
| `adjudicate` (967-1074) | write | **anyone** | CHALLENGED | commitment_id, content, evidence_json, challenge_statement, disputed_ids_json, challenge_evidence_json | `adjudications[aid]`, status -> ADJUDICATED (only after consensus) | **yes** | + HASH_MISMATCH, `[LLM_ERROR]`, consensus failure | adjudication id |
| `compute_commitment_id` (1079) | view | anyone | - | requester (hex), nonce | none | no | INVALID_INPUT | id |
| `get_limits` (1089) | view | anyone | - | - | none | no | - | limits object |
| `get_commitment` (1111) | view | anyone | - | commitment_id | none | no | NOT_FOUND | record + derived child ids |
| `get_submission` (1133) / `get_challenge` (1158) / `get_adjudication` (1177) | view | anyone | - | id | none | no | NOT_FOUND | record |

Storage: `commitments`, `commitment_status`, `submissions`, `challenges`, `adjudications` (`TreeMap`s, lines 797-803); records (734-795) are written once. No events are emitted. No payable methods.

## 5. State machine (implemented vs. intended)

The implementation stores one status per commitment (`commitment_status`); submission/challenge statuses are derived in views (1133-1175). Intended lifecycle in the prompt (section 1.3) vs. implementation: **identical** transitions and callers, with one semantic discrepancy (AR-01: which criteria are adjudicated).

| From | Method | Caller | To | Irreversible | Repeatable | Partial state on failure |
|------|--------|--------|----|--------------|------------|--------------------------|
| - | create_commitment | anyone | OPEN | - | no (id exists) | none (tested) |
| OPEN | accept | executor | ACCEPTED | yes | no | none |
| OPEN | reject | executor | REJECTED (terminal) | yes | no | none |
| OPEN | cancel | requester | CANCELLED (terminal) | yes | no | none |
| ACCEPTED | submit_delivery | executor | SUBMITTED | yes | no | none |
| SUBMITTED | create_challenge | requester | CHALLENGED | yes | no | none |
| SUBMITTED | close_uncontested | requester | UNCONTESTED (terminal) | yes | no | none |
| CHALLENGED | adjudicate | anyone | ADJUDICATED (terminal) | yes | no | none; failed attempts retryable |

Evidence (executed, stub): `A5_actor_by_operation_matrix` (7 operations x 3 actors), `A6_terminal_states_are_closed` (4 terminal states x 7 operations, state unchanged), `A2_ModelBasedRandomWalk` (**20,000 random steps**, 1,606 successes, 18,353 rejections, 41 simulated consensus failures; contract and an independent reference model agreed after every step; commitment records never changed after creation; every failed step left the full storage snapshot identical). `ACCEPTED` and `SUBMITTED` can last forever (intended V1 limitation, AR-13). `CHALLENGED` can also last forever (AR-02).

## 6. Authorization (spec section 8)

All authorization checks use `gl.message.sender_address` compared with the stored `Address` (lines 863-965). No method accepts a "caller" argument. `adjudicate` has no caller check by design.

| Check | Result | Evidence |
|-------|--------|----------|
| Only requester challenges / cancels / closes | PASS | A5 matrix |
| Only executor accepts / rejects / submits | PASS | A5 matrix |
| Relayer cannot change inputs, requester, executor, verdict | PASS (every altered input -> HASH_MISMATCH; verdict only from consensus) | `A5_relayer_has_no_authority...` |
| Adjudication impossible without a challenge | PASS (INVALID_STATE in OPEN/ACCEPTED/SUBMITTED, 0 LLM calls) | `A5_no_adjudicate_without_challenge...` |
| UNCONTESTED cannot be challenged/adjudicated | PASS | `A5_uncontested_cannot_be_challenged...` |
| Executor cannot impersonate requester | PASS | matrix |

## 7. Evidence and submission integrity (spec section 7)

- Hash inputs: `_content_hash` (436) binds `commitment_id` + content; manifest hash binds `commitment_id` + canonical (id-sorted) items; challenge hash binds `submission_id` + requester + statement + sorted disputed ids + items; `_package_hash` (459) binds commitment, submission and challenge hashes. Encoding is type-tagged and length-prefixed (`_enc_into`), so it is injective; domains are separated (`_hash`, 400).
- Verification: lines 1002-1007 recompute and compare **before** any LLM call (LLM call counter = 0 in all mismatch tests).
- The leader and validators evaluate the same re-supplied, hash-verified `ctx` (1010-1021); they do not read storage inside the nondeterministic block (AST check: the only `self.` writes in `adjudicate` are at lines 1057 and 1073, after the call at 1045; the nested functions contain no `self` reference).
- Byte-exactness (executed): NFC vs NFD, CRLF vs LF, trailing space, BOM, zero-width space, Cyrillic homoglyph, truncation, tab, case: **all 9 -> HASH_MISMATCH**; the exact original still adjudicates. Evidence-manifest variants (6) all rejected. Cross-record substitution (A's material for B and the reverse, and mixed bytes) all rejected; identical bytes in two commitments yield distinct commitment/package hashes and isolated results.
- Content is `str`; **binary content is not representable** except as encoded text (documented design limit).
- The contract does **not** claim to verify URLs: kind `EXTERNAL_REFERENCE` is stored as text; a `MET` cannot rest only on such items (line 530). No web access exists (`gl.nondet.web` absent, checklist item).

## 8. Record identifiers and concurrency (spec section 9)

Ids are derived, not allocated (`_commitment_id`: requester + nonce; child ids hash the parent id). No counters, no shared "latest" variable, no list/array positions. Executed: 8 commitments with the same requester/executor, interleaved partial adjudications, exact lookups returned the right records; same nonce across requesters/executors gives distinct ids; 20,000-step random walk. **Concurrency semantics of the real network (ordering of simultaneous transactions) are NOT VERIFIED**; the contract's per-call atomicity (failed call = no state change) is tested.

## 9. Replay and duplication (spec section 13)

Every write is protected by a status check (and creation by an existence check). Tested: duplicate create/accept/reject/cancel/submit/challenge/close/adjudicate, calls in every terminal state, retries after failure. Result records are never overwritten (AR-09 notes a redundant guard).

## 10. Prompt injection (spec section 10)

Design (lines 584-668): instructions are contract text; all participant text sits in one single-line JSON `DATA` document produced with `ensure_ascii=True`, so quotes, newlines, control and non-ASCII characters are escaped; the model's output is reduced by the contract to enums and ids validated against the committed package; the leader proposal carries **no free text**, so injection cannot travel to validators through the proposal; the validator's evaluator call never sees the leader's claim.
Executed (stub): 6 injection payloads (fake system text, delimiter break-outs, role tokens, bidi/confusables) stay inside the JSON string and out of the instruction area (existing tests, re-run). **Real LLM susceptibility is NOT VERIFIED** and cannot be bounded by code (AR-07). Same-content manipulation of both leader and validator is possible in principle because both use the same prompt on the same data; the verifier uses a different role prompt but the same data.

## 11. Input bounds and resource exhaustion (spec section 11)

All limits are enforced before any expensive step (lines 95-111, 145-304). Measured (CPython, stub): all eight 300 KB probes rejected in <= 0.2 ms with 0 LLM calls; maximum valid inputs: deterministic work 0.5-2.5 ms per call. Hash fallback: 0.086 s per 32 KB of pure-Python Keccak (only when the SDK's `Keccak256` is unavailable; cost inside GenVM UNVERIFIED, AR-14).
**Prompt size at maximum valid input: 40,448 bytes (evaluator) / 41,448 (verifier) for ASCII, but 113,788 / 114,788 bytes when the same byte budget is spent on astral characters** (2.81x), because `ensure_ascii=True` turns each 4-byte character into a 12-byte surrogate-pair escape. The docs state ~37 KB (AR-03, AR-05).

## 12. Error handling and retries (spec section 12)

| Failure | Behaviour (source) | Business verdict? |
|---------|--------------------|-------------------|
| Business-rule / auth / state / input / hash | `_fail` -> `UserError("[EXPECTED] CODE...")`, deterministic strings (checked: no formatting with variable data in `_fail` calls) | no |
| Malformed LLM output, LLM exception (leader) | `UserError("[LLM_ERROR] ...")` (1027-1028); validators return `False` for any non-`Return` leader result (1032-1034) | no |
| Validator exception / disagreement | `except Exception: return False` (1042-1043) | no |
| No majority | transaction fails / `UNDETERMINED` per official docs; storage untouched | no |
| Accepted but non-canonical proposal | `UserError("[LLM_ERROR] accepted proposal failed deterministic re-check")` (1048-1051) | no |

A failed adjudication leaves `CHALLENGED` (executed: 41 simulated consensus failures, state identical; retry succeeds). **Recoverable:** transient failures. **May get stuck:** persistent failure (AR-02, AR-03).

## 13. GenVM v0.4 / SDK compatibility (spec section 14)

Static checklist against the v0.4 migration guide (`A9_SdkCompatibilityStatic`, executed, 18/18 PASS, `stats.json`): runner header lines 1-2; `import genlayer as gl` (8); `from genlayer.types import *` (9); `gl.contract.Contract` (797); `@gl.storage.allow` (732); `gl.storage.TreeMap` (798); `gl.vm.run_nondet_default` (1045); single-string `UserError` (1028); **absent**: `run_nondet`/`run_nondet_unsafe`, `__receive__`, `salt_nonce`, `from genlayer import *`, `gl.Contract`, `allow_storage`, `gl.message_raw`, `gl.eq_principle`, `gl.nondet.web`, `response_format`; special methods undecorated. Python/SDK/CLI versions **cannot be inspected**: nothing installed. **Runtime compatibility is NOT VERIFIED** (the first delivery of this contract passed the author's harness and still failed to deploy because of its header; the header is now regression-tested, but that class of error is invisible without the real Studio).

## 14. Storage and deterministic execution (spec section 15)

- Types: `str`, `Address`, `u32` in `@gl.storage.allow` dataclasses; `TreeMap[str, record]` and `TreeMap[str, str]` (734-803). No lists/dicts in storage; structured values are JSON strings.
- Nondeterministic functions capture only `ctx` (free variables: exactly `('ctx',)` for both; `ctx` is JSON-serialisable). `cloudpickle` round-trip of both closures executed successfully, including running the unpickled functions. Real GenVM pickling (`direct_vm.check_pickling`): NOT VERIFIED.
- Determinism: no `set`/`frozenset` iteration (AST), 25 loops reviewed (iterables in `stats.json`), no floats, time, randomness or I/O; `sorted`/sorted-key ordering is explicit.
- Persisted result equals the accepted value: `_check_proposal` forces canonical equality (562-581) and the stored `criteria_results_json` is exactly that list; tested (`A3_stored_result_equals_accepted_proposal`).
- Real storage serialisation, aliasing and `Address`/`u32` field construction: **NOT VERIFIED**.

## 15. Frontend-facing interface (spec section 16)

Unambiguous: argument names/types (all `str`), preconditions, derived ids, `get_*` by exact id, `compute_commitment_id`, `get_limits`, UNCONTESTED vs ADJUDICATED are distinct statuses and `adjudication_id == ""` for the former. Ambiguities and gaps: AR-10 (no enumeration or events, write return values unreliable by design, `created_at` format unverified, no deployment configuration, fee handling lives only in documentation). Fees (Studio v0.123): tests and docs mention them; the repository has no deploy script or fee-aware test configuration and the integration tests were never run.

## 16. Invariants (spec section 19)

| Invariant | Enforcing code | Result |
|-----------|----------------|--------|
| One requester and one executor; not confusable | 822-860, `Address` equality, `executor != requester` | HELD (tests) |
| Submission -> one commitment; challenge -> one submission; adjudication -> one challenge | derived ids 408-420, stored parent ids | HELD |
| Only requester creates/cancels OPEN; only executor accepts/rejects/submits; only requester challenges; anyone relays | 863-965, 967 | HELD |
| Criteria immutable after acceptance; submission/challenge not replaceable | records written once (AST/regex check: each map has exactly one assignment) | HELD |
| Evidence matches original commitment | 1002-1007 | HELD |
| Adjudication references the exact disputed submission | ids + `_package_hash` | HELD |
| Stored result == accepted consensus result | 1048-1073 | HELD (logic); real consensus NOT VERIFIED |
| No invalid transition; terminal states closed; UNCONTESTED != ADJUDICATED; challenge cannot be bypassed; failed adjudication does not finalize | status gates | HELD (20,000-step walk) |
| Every material criterion independently evaluated; unsupported evidence refs, missing/invented/duplicate/contradictory results rejected; overall consistent; no free text | 489-581, 1031-1043 | HELD (12,303 mutations) |
| A validator does not merely check formatting | outcome equality + verifier | HELD (counterfactual weak validator accepts a forgery that the real one rejects) |
| No unverified result is persisted | persistence after 1045 | HELD (AST) |

## 17. Findings

Summary: CRITICAL 0 - HIGH 0 - **MEDIUM 3** - LOW 3 - INFORMATIONAL / LIMITATIONS 8.

### AR-01 MEDIUM - Undisputed criteria are evaluated and can change the overall result

**Project:** AgentRecall V1
**Location:** `contracts/agent_recall.py` 1010-1021 (`ctx["criteria"]` is the full committed list; disputed ids only passed as context), 584-599 (`_data_block`), 619-641 (evaluator rules R7: one result for every criterion), 489-538 (`_canonical_results` demands a result for every committed criterion)
**Affected method:** `adjudicate`
**Category:** CONFIRMED (spec discrepancy; product-logic)
**Expected invariant:** Binding spec 1.3 step 6: "Adjudication evaluates the **disputed** criteria using the agreed commitment and exact submitted evidence."
**Actual behavior:** all committed criteria are evaluated and persisted; `overall_outcome` is derived from all of them.
**Attack or failure sequence:** requester challenges only `C1`; the evaluator returns `C1 MET`, `C2 NOT_MET`, `C3 MET`; result `PARTIALLY_FULFILLED`, driven by the undisputed `C2` that the requester never contested.
**Impact:** a result the requester did not ask for; an executor can lose on a criterion that was accepted implicitly. This is the most likely source of "strange results after verification". Recorded by the author as decision E12 and flagged to the owner, but never confirmed by the owner.
**Evidence:** `audit/harness/audit_harness.py::A10_SpecDiscrepancies` -> `disputed=['C1']`, criteria sent to the LLM `['C1','C2','C3']`, overall `PARTIALLY_FULFILLED`, undisputed results `[('C2','NOT_MET'),('C3','MET')]` (`evidence/stats.json`).
**Reproduction status:** Confirmed (logic, stub).
**Remediation direction:** owner decision. Smallest change if the spec is authoritative: build `ctx["criteria"]` from the disputed ids only (and define `overall_outcome` over them). If E12 is accepted: keep the code and make the UI state that every criterion is re-evaluated.
**Regression test required:** challenge `C1` only; assert result list == disputed ids (or, if E12 stays, assert the UI/doc text).

### AR-02 MEDIUM - No exit from CHALLENGED if adjudication can never complete

**Location:** 917-956 (`create_challenge`, no withdrawal), 959-965 (`close_uncontested` requires SUBMITTED), 967-1074 (the only transition out of CHALLENGED)
**Affected method:** `adjudicate`, `create_challenge`
**Category:** CONFIRMED (structure); likelihood UNVERIFIED
**Expected invariant:** the spec accepts only "ACCEPTED may stay indefinitely"; it does not accept other permanent states.
**Actual behavior:** with the LLM unavailable, `accept/reject/cancel/close_uncontested/submit/create_challenge` all fail `INVALID_STATE` and `adjudicate` fails consensus: the commitment stays `CHALLENGED`.
**Sequence:** requester challenges; adjudication keeps failing (provider down, persistent validator disagreement, or content that makes the LLM unstable/too large - see AR-03); nobody can finish or withdraw.
**Impact:** permanent workflow block; no funds or penalties exist in V1, so impact is on workflow and user experience, not value. The executor controls the delivery text, so it can influence AR-03.
**Evidence:** `A6_no_exit_from_challenged_except_adjudicate` (`stats.json: A6_exits...`).
**Reproduction status:** Confirmed (structure). Real-network persistence of the failure: UNVERIFIED.
**Remediation direction:** owner decision on a new transition (for example a requester-only withdrawal of an unadjudicable challenge) or an explicit documented operational answer. Not implemented here.
**Regression test required:** the chosen exit (or documentation) with a test that no verdict is recorded.

### AR-03 MEDIUM (impact UNVERIFIED) - Prompt size can reach ~114 KB because of `ensure_ascii` escaping

**Location:** 597-599 (`json.dumps(..., ensure_ascii=True)`), limits 95-111 (byte-based, not escaped-size based)
**Affected method:** `adjudicate` (evaluator and verifier calls, leader and every validator)
**Category:** CONFIRMED (measurement); consequences SUSPECTED / UNVERIFIED
**Expected invariant:** inputs bounded so that the LLM call is reliable; docs say ~37 KB.
**Actual behavior:** same 6,000 + 16,000 + 1,500 + 8,000 + ... byte budget: 40,448 bytes of prompt with ASCII, **113,788** (evaluator) and **114,788** (verifier) with astral characters (factor 2.81).
**Sequence:** an executor submits maximum-size content made of astral characters (still within every byte limit); the requester challenges; every adjudication attempt sends ~114 KB to several LLMs.
**Impact:** depending on provider context limits: LLM errors -> repeated failure -> AR-02 permanent `CHALLENGED`; or, if a provider *silently truncates*, a verdict computed on partial data (the challenge section is the **last** part of `DATA`, so truncation would remove the requester's allegation and evidence first). Silent truncation by providers is **SUSPECTED, not verified**.
**Evidence:** `A8_PromptAndResourceBounds` (`stats.json: A8_max_ascii`, `A8_max_astral`, `A8_astral_inflation_factor_eval`).
**Reproduction status:** Confirmed numerically; provider behaviour UNVERIFIED.
**Remediation direction:** bound the **escaped** prompt data deterministically before any LLM call (reject above a fixed size), or lower byte limits accordingly; update documentation.
**Regression test required:** maximum astral input is rejected deterministically or measured under the chosen bound.

### AR-04 LOW - Duplicate JSON object keys are accepted (last key wins)

**Location:** 198-219 (`_parse_json_list` uses `json.loads` defaults), 251-287
**Category:** CONFIRMED
**Actual behavior:** `[{"id":"E1","id":"E2","kind":"TEXT","content":"x"}]` is accepted and stored as id `E2`.
**Impact:** none on integrity (the hash covers the parsed value, so evaluated == committed), but a client that signs or inspects the JSON text sees a different meaning than the contract.
**Evidence:** `A4_duplicate_json_keys_last_wins_is_deterministic`.
**Remediation direction:** reject duplicates with an `object_pairs_hook` (standard library). **Regression test:** duplicate key -> `INVALID_JSON`/`INVALID_INPUT`.

### AR-05 LOW - DOCUMENTATION DISCREPANCY: largest prompt documented as ~37 KB

**Location:** `docs/DEPLOYMENT_READINESS.md:97`, `docs/SECURITY_AUDIT.md:29`, `docs/TEST_REPORT.md:207` (generated by `tools/gen_test_report.py`, which should be edited at its source)
**Actual:** 40.4 KB (ASCII) to 113.8 KB (astral). **Remediation:** correct the figure once AR-03 is decided. Not modified by this audit.

### AR-06 INFORMATIONAL (DESIGN LIMITATION) - reason codes and cited evidence are verified, not compared for equality

Decision E9 (consistent with the binding "do not require identical prose"). Under an *always-SUPPORTED* verifier mock, 306 of 12,303 mutated proposals were accepted: **293 changed only `evidence_ids`, 13 only `reason_codes`, 0 changed an outcome, overall, id or hash**. Real verifier behaviour NOT VERIFIED. Accepted risk: a leader may attach plausible but suboptimal citations to a correct outcome.

### AR-07 INFORMATIONAL (DESIGN LIMITATION) - guarantees that depend on LLMs

Shared model bias, verifier anchoring on the proposed claims, residual prompt-injection persuasion, and liveness failures (honest validators disagreeing on borderline criteria) cannot be removed by contract code and were **not testable without real LLMs**.

### AR-08 INFORMATIONAL - JSON depth guard counts below zero; imprecise error text

**Location:** 174-195. `_json_depth_ok("]]]]][[[[[", 2)` returns True; `json.loads` rejects that text at its first character, so no deep structure is ever parsed: not exploitable. `kind` given as a list yields "nested too deeply" (the guard triggers at depth 3), which is a misleading message.

### AR-09 INFORMATIONAL - redundant guard (equivalent mutant)

**Location:** 1054-1055. `ALREADY_EXISTS` for an adjudication is unreachable while the state machine holds. Deleting it changes no behaviour (mutant survived by design). Harmless defence in depth.

### AR-10 INFORMATIONAL - Frontend integration gaps

No events and no on-chain enumeration: an executor cannot discover commitments addressed to them from the contract alone; the frontend must track ids off-chain (the requester can derive ids from nonces). Write return values are unreliable as a transport (the docs already tell clients to use views). `created_at` (`gl.message.raw["datetime"]`) format unverified. The repository has no deployment script, `gltest` configuration or fee-aware test setup (Studio v0.123 requires fees on every deploy/write).

### AR-11 UNVERIFIED - real-runtime behaviours

Schema loading and runner acceptance on the real toolchain; `Address`/`u32` dataclass construction and `TreeMap` assignment; closure serialisation inside GenVM; `exec_prompt` text output and `gl.vm.Return`/`UserError` behaviour; what `run_nondet_default` does when `validator_fn` returns `False` for a leader error (rotation vs. immediate failure); consensus rotation, `UNDETERMINED`, finality and appeals; real transaction ordering.

### AR-12 MISSING TEST COVERAGE

Official Direct Mode tests (`tests/direct/`, 23 functions) and Studio tests (`tests/integration/`, 5 functions) were never executed; no Studio tests with mocked validators for the 15 rejection scenarios exist; `genvm-lint check`/`schema` not run; no test with a real LLM.

### AR-13 INFORMATIONAL (intended V1 limitation)

`ACCEPTED` and `SUBMITTED` may last indefinitely. Not a vulnerability.

### AR-14 LOW (UNVERIFIED) - pure-Python Keccak fallback cost inside GenVM

Only used if the SDK's `Keccak256` cannot be imported or fails; 0.086 s per 32 KB in CPython; cost in GenVM unknown. If both fallbacks are needed at maximum input, deterministic execution cost could be significant.

## 18. Required final questions

| # | Question | Answer | Basis |
|---|----------|--------|-------|
| 1 | Does only the requester create commitments? | **YES** | the creator becomes the requester; ids are bound to the sender (822-860) |
| 2 | Does only the executor accept or reject? | **YES** | A5 matrix |
| 3 | Can only the executor submit? | **YES** | A5 matrix |
| 4 | Can only the requester initiate a challenge? | **YES** | A5 matrix |
| 5 | Can any address relay adjudication after a valid challenge? | **YES** | A5 matrix |
| 6 | Can the relayer alter the adjudication inputs? | **NO** | hash verification, 5 alteration types x 2 relayers |
| 7 | Can the requester cancel after acceptance? | **NO** | `INVALID_STATE` |
| 8 | Can a commitment be finalized without the lifecycle steps? | **NO** | 20,000-step walk + matrices |
| 9 | Is UNCONTESTED distinct from ADJUDICATED? | **YES** | distinct status; no adjudication record |
| 10 | Is the exact original submission bound to the adjudication? | **YES** (logic) | package hash; real runtime NOT VERIFIED |
| 11 | Are evidence hashes verified against the actual supplied bytes? | **YES** | 9 + 6 variants |
| 12 | Can evidence from another submission be substituted? | **NO** | cross-record tests |
| 13 | Does the validator receive the actual leader result? | **YES** (by source, 1031-1036) | real runtime NOT VERIFIED |
| 14 | Does the validator independently evaluate the complete decision-critical result? | **PARTIALLY** | outcomes: independent evaluation + exact equality; reason codes/evidence ids: structural checks + LLM verifier by design (AR-06) |
| 15 | Can a missing criterion result be accepted? | **NO** | mutation fuzz |
| 16 | Can an invented criterion result be accepted? | **NO** | mutation fuzz |
| 17 | Can a materially contradictory result be accepted? | **NO** | 0 / 12,303 (relative to the validator's own evaluation; LLM correctness not testable) |
| 18 | Can the overall verdict contradict the criterion outcomes? | **NO** | derived and re-checked (562-581) |
| 19 | Can a technically failed LLM operation become a business verdict? | **NO** within the contract; provider-side silent truncation **NOT VERIFIED** (AR-03) | |
| 20 | Can a failed adjudication permanently corrupt state? | **NO** corruption, but **PARTIALLY**: it can leave the commitment permanently `CHALLENGED` (AR-02) | |
| 21 | Can duplicate calls overwrite an existing result? | **NO** | |
| 22 | Can concurrent commitments cause record confusion? | **NO** (logic); real concurrency semantics **NOT VERIFIED** | |
| 23 | Can prompt injection manipulate adjudication? | **NOT VERIFIED** | structural mitigations only; no real LLM |
| 24 | Can oversized input exhaust execution resources? | **PARTIALLY** | deterministic parts bounded and fast; LLM prompt up to ~114 KB (AR-03) |
| 25 | Is the contract compatible with its intended GenVM and SDK? | **PARTIALLY** | static v0.4 checklist 18/18; runtime NOT VERIFIED |
| 26 | Have storage and serialization paths been verified? | **NOT VERIFIED** | closure pickling checked with cloudpickle only |
| 27 | Have Direct Mode adversarial tests been executed? | **PARTIALLY** | equivalent logic tests ran against a stub; official Direct Mode did not |
| 28 | Has Localnet integration testing been executed? | **NO** | |
| 29 | Are frontend-facing methods and lifecycle transitions unambiguous? | **PARTIALLY** | AR-10 |
| 30 | Which core security properties remain unverified? | see list | real consensus behaviour; real LLM correctness and injection resistance; real storage/serialization; runtime schema load; fee-aware deploy/write flow; real concurrency/finality/appeals |

## 19. Not claimed

No test marked "executed" ran on GenVM, Studio or a real LLM. Hash tests use the stub's SHA3-256 for the SDK path; the contract's own Keccak-256 fallback is verified against published vectors. Nothing here proves truth of any adjudication: GenLayer consensus is majority-based, and validators' intermediate LLM answers are not stored by the contract.
