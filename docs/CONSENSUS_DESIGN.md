# AgentRecall V1 - Consensus design

## 1. API choice

`gl.vm.run_nondet_default(leader_fn, validator_fn)` is used.

Verified from the SDK reference (https://sdk.genlayer.com/main/_static/ai/api.txt, v0.4.0-rc1):

- `run_nondet_default(leader_fn, validator_fn, /, *, compare_user_errors=..., compare_vm_errors=..., custom_runners=None, catch_vm_error=False) -> T`.
  `validator_fn: Callable[[Result[T]], bool]` receives the **leader's actual `Result`**
  (`Return | VMError | UserError`) and runs **in a sandbox**; the reference calls it "the
  recommended API for custom non-deterministic execution".
- `Return` carries the leader value in `.calldata`.
- The generic `gl.vm.run_nondet` is the *unsafe* variant: "does not use extra sandbox for catching
  validator errors"; a validator error becomes a "Disagree". The migration guide warns that
  code written for the old `run_nondet` silently changes meaning. It is **not** used here.

Not verifiable in this environment: the runtime behaviour of the above inside a real GenVM.

## 2. Execution path

```
adjudicate(...)                                  [deterministic]
  1  auth: none (permissionless)
  2  state: commitment must be CHALLENGED
  3  validate + normalize all re-supplied material (size, charset, JSON depth, ids, kinds)
  4  recompute content / manifest / challenge hashes; compare with stored -> HASH_MISMATCH
  5  build ctx (plain Python data only) incl. evidence_package_hash
  ----------------------------------------------------------------------------------
  run_nondet_default(leader_fn, validator_fn)    [non-deterministic; no storage access]
     leader_fn:  1 LLM call (evaluator, plain text answer parsed as JSON by the contract)
                 -> strict normalization -> proposal dict (no free text)
                 any failure -> UserError("[LLM_ERROR] ...")
     validator_fn(leader_result):
                 a  not a Return?                         -> False
                 b  deterministic re-check of the proposal -> else False
                 c  own independent evaluator call         (never sees the leader's claim)
                 d  every criterion: own outcome == proposed outcome   -> else False
                 e  verifier call on the proposed claims (all SUPPORTED) -> else False
                 f  any exception anywhere                 -> False
  ----------------------------------------------------------------------------------
  7  re-run the deterministic proposal check on the accepted value (defence in depth)
  8  persist Adjudication, set status ADJUDICATED         [deterministic, after consensus]
```

All storage writes are after step 6. `leader_fn`/`validator_fn` capture only a plain `ctx`
dict and module-level pure functions; they never touch `self`. A harness test asserts that
`leader_fn` contains no `self.` and that writes occur after the block.

## 3. The proposal (decision-critical result)

```
{ "schema_version": 1,
  "commitment_id": "<hex>", "submission_id": "<hex>", "challenge_id": "<hex>",
  "evidence_package_hash": "<hex>",
  "overall_outcome": "FULFILLED | PARTIALLY_FULFILLED | NOT_FULFILLED | INDETERMINATE",
  "criteria_results": [
     { "criterion_id": "C1", "outcome": "MET | NOT_MET | INDETERMINATE",
       "reason_codes": ["..."], "evidence_ids": ["S:#DELIVERY", "S:E1"] } ... ] }
```

There is **no free-text field**. Every string is either a hash, a committed criterion id, a
member of a closed vocabulary, or an id validated against the committed evidence package.
Consequently:

- a leader cannot smuggle prose or instructions to validators through the proposal;
- "changing only explanatory prose" is impossible by construction (tested:
  `test_prose_only_differences_cannot_exist_in_the_proposal`);
- the leader's LLM text never reaches the verifier prompt except as validated enum values/ids.

## 4. What the validator checks

| # | Check | Kind | Where |
|---|-------|------|-------|
| 1 | Leader result is a successful `Return` before `.calldata` is read | deterministic | `validator_fn` |
| 2 | Exact key set; `schema_version == 1` (strict int, bool rejected) | deterministic | `_check_proposal` |
| 3 | `commitment_id`, `submission_id`, `challenge_id`, `evidence_package_hash` equal the contract's own recomputed values | deterministic | `_check_proposal` |
| 4 | Every committed criterion appears exactly once; no missing / duplicate / unknown ids | deterministic | `_canonical_results` |
| 5 | `outcome` in vocabulary; reason codes allowed for that outcome, 1-2, unique | deterministic | `_canonical_results` |
| 6 | Evidence ids exist in the committed package; unique; <= 8 | deterministic | `_canonical_results` |
| 7 | `MET` cites >= 1 non-`EXTERNAL_REFERENCE` item | deterministic | `_canonical_results` |
| 8 | Results are in canonical order and canonical (sorted) lists | deterministic | `_check_proposal` |
| 9 | `overall_outcome` equals the value derived from the criterion results | deterministic | `_check_proposal` |
| 10 | Own independent evaluation from the committed input; **per-criterion outcome must be identical** | LLM, independent | `_evaluate`, `validator_fn` |
| 11 | Verifier: every criterion's claim (outcome, reason codes, cited evidence) is SUPPORTED by the evidence | LLM, independent | `_verify_claims` |

Checks 4-9 are exact and cannot be softened by LLM behaviour. No score or numeric tolerance
exists anywhere.

### Why reason codes / evidence ids are verified, not compared for equality

Decision E9 (follows binding decision B1). Two honest evaluations frequently cite different
evidence or choose different reasons for the same outcome. Exact equality there would make
consensus fail for harmless differences. Outcomes - the only fields that change a business
decision - are compared exactly; reasons and citations are checked structurally and by an
independent verifier. **Residual risk:** a leader that picks a plausible but suboptimal reason
code or citation for a correct outcome can pass if the verifier judges it supported.

## 5. Failure handling (fail-closed)

| Situation | Behaviour | State |
|-----------|-----------|-------|
| Leader returns a valid proposal | validators run section 4 | persisted only if consensus accepts |
| Leader LLM output malformed / wrong shape / unknown enum | leader raises `[LLM_ERROR]`; validators return `False` (leader result not a `Return`) | unchanged |
| Leader raises user error / VM error | not a `Return` -> `False` | unchanged |
| Validator's own evaluation differs on any criterion outcome | `False` | unchanged |
| Validator cannot reach / parse the LLM | exception caught -> `False` | unchanged |
| Validator finds missing / unsupported / contradictory content | `False` | unchanged |
| Verifier says any claim UNSUPPORTED or answers malformed | `False` | unchanged |
| Validator code itself throws | caught -> `False` (and the sandbox of `run_nondet_default` also contains it) | unchanged |
| Transient infrastructure error | same as LLM unavailable | unchanged |
| No majority | per the official transaction docs, the transaction returns to `PROPOSING` with a new leader; after all rotations it becomes `UNDETERMINED` | unchanged; retry with a new transaction |

`INDETERMINATE` as a **business result** (a criterion or the overall outcome that the evidence
cannot decide) is persisted. A **technical failure** is never converted into `INDETERMINATE`;
it persists nothing.

## 6. Limitations (must be shown to users)

- Agreement under this rule is not proof of truth. The contract establishes only that a leader
  proposal was accepted under the rule above. It cannot establish authenticity of submitted
  material, identity of authors, accessibility of referenced URLs, or independence of validators'
  underlying models; shared model bias is possible.
- Per the official docs the protocol requires a **majority**, not unanimity. A single dissenting
  validator cannot always block a transaction. This design makes each validator reject materially
  incorrect proposals; it does not claim a veto.
- Validators' intermediate LLM answers are not stored on-chain. What is stored is the leader's
  accepted result.
- Liveness: independent LLM runs can disagree on borderline criteria, causing rotation or
  `UNDETERMINED`. The `INDETERMINATE` outcome and explicit rules in the evaluator prompt are
  there to reduce this; it cannot be eliminated.
- Each adjudication costs one leader evaluation plus, per validator, two LLM calls.
- Prompt injection is mitigated, not eliminated: see `THREAT_MODEL.md`.
- Behaviour of `run_nondet_default` when `validator_fn` returns `False` for a leader *error*
  (rotation vs. immediate failure) is documented for the older API name in the error-handling
  page; for the current name it must be confirmed in Studio (see `TEST_REPORT.md`).
