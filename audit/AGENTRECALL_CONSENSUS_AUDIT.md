# AgentRecall V1 - Consensus audit

Audited commit `4c50da760bdd997eba9e0f6e954efae49e83f907` (`contracts/agent_recall.py`, SHA-256 `64575c67...b5e9d`). Read-only. All "executed" results ran against a dev-only SDK stub; real consensus was **not** exercised.

## 1. SDK API actually used

`gl.vm.run_nondet_default(leader_fn, validator_fn)` (line 1045). Per the SDK reference and v0.4 migration guide: the validator function receives the leader's `Result` (`Return | VMError | UserError`), runs in a sandbox, and returns a boolean; the generic `gl.vm.run_nondet` is the *unsafe* variant and is **not** used (static checklist, `A9`). `gl.nondet.exec_prompt(prompt)` is called in plain text mode inside the nondeterministic functions only (lines 716-725). No `gl.eq_principle`, no web access.

## 2. The leader function (lines 1024-1029)

```
def leader_fn():
    try:
        results = _evaluate(ctx)            # 1 LLM call, strict normalisation
    except Exception:
        raise gl.vm.UserError("[LLM_ERROR] leader evaluation failed")
    return _build_proposal(results, ctx)
```
Inputs: a plain `ctx` dict built deterministically *before* the block from re-supplied material whose hashes were already verified (lines 1010-1021): commitment id/description/criteria/accepted kinds, delivery text, executor evidence, requester evidence, challenge statement, disputed ids, and the contract-computed ids and evidence-package hash. `ctx` is the only captured variable (`co_freevars == ('ctx',)`, executed) and is JSON-serialisable. Inputs are immutable between submission and adjudication: records are write-once and the material is re-verified against hashes inside the same transaction.

## 3. The leader result schema

```
{ schema_version: 1, commitment_id, submission_id, challenge_id, evidence_package_hash,
  overall_outcome: FULFILLED | PARTIALLY_FULFILLED | NOT_FULFILLED | INDETERMINATE,
  criteria_results: [ { criterion_id, outcome: MET | NOT_MET | INDETERMINATE,
                        reason_codes: [1-2 from a per-outcome closed list],
                        evidence_ids: [0-8 ids from the committed package] } ... ] }
```
No free-text field exists. Every string is a hash, a committed criterion id, a member of a closed vocabulary, or an id validated against the committed package. Consequently a leader cannot smuggle prose or instructions to validators or to the stored record.

## 4. The validator function (lines 1031-1043)

```
def validator_fn(leader_result) -> bool:
    if not isinstance(leader_result, gl.vm.Return):  return False        # 1032-1034
    try:
        proposed = _check_proposal(leader_result.calldata, ctx)           # 1036  deterministic
        own = _evaluate(ctx)                                              # 1037  independent LLM call
        for mine, theirs in zip(own, proposed):                           # 1038-1040
            if mine["criterion_id"] != theirs["criterion_id"] or mine["outcome"] != theirs["outcome"]:
                return False
        return _verify_claims(ctx, proposed)                              # 1041  second LLM call
    except Exception:
        return False                                                      # 1042-1043
```

| Required check (audit 6.4) | Implemented? | Where |
|----------------------------|--------------|-------|
| Validator receives `Result[T]` and checks `Return` before `.calldata` | **Yes** | 1031-1036 |
| Evaluates the actual leader proposal | **Yes** | 1036, 1041 |
| Independently inspects the same evidence | **Yes**: builds its own prompt from the same hash-verified `ctx`; does not see the leader's claims | 1037 |
| Checks every decision-critical field | **Yes** (see table 5) | 489-581, 1038-1041 |
| Meaningful accept/reject | **Yes** | boolean |
| Exceptions handled safely | **Yes**: any exception -> `False` | 1042-1043 |
| Accepted leader result == stored value | **Yes** | 1048-1073; `_check_proposal` demands canonical equality |
| No storage mutation inside the block | **Yes** (AST: nested functions have no `self`; writes only at 1057 and 1073, after 1045) | executed |

## 5. Decision-critical fields and how each is verified

| Field | Verification | Exact? |
|-------|--------------|--------|
| `schema_version` | strict int equality (bool/float rejected) | exact |
| `commitment_id`, `submission_id`, `challenge_id`, `evidence_package_hash` | equal to the contract's own recomputed values | exact |
| criterion set | every committed criterion exactly once; no missing, duplicate, unknown | exact |
| result order and canonical form | must equal the canonical re-serialisation | exact |
| `outcome` per criterion | closed vocabulary **and** equal to the validator's own independent evaluation | **exact, independent** |
| `overall_outcome` | equal to the value derived from the criterion outcomes (`_derive_overall`, 541) | exact (derived) |
| `reason_codes` | closed vocabulary partitioned by outcome, 1-2 unique codes | structural + verifier (not equality) |
| `evidence_ids` | each exists in the committed package, unique, <= 8; `MET` needs one non-`EXTERNAL_REFERENCE` item (line 530) | structural + verifier (not equality) |
| semantic support of outcome + reasons + citations | second, independent LLM call (`_verify_claims`) must answer SUPPORTED for **every** criterion | LLM |

## 6. Independent evidence verification

Both LLM calls receive the whole evidence package and the commitment (never the leader's prose). The verifier additionally receives the proposed claims, which contain only enum values and validated ids (so claims cannot carry injected text). Rule R9 of the verifier prompt tells it to re-derive the answer rather than defer to the proposal. **Whether a real LLM follows that rule (anchoring) is NOT VERIFIED.**

## 7. Contradiction, omission and fabrication tests (executed, stub)

| Test | Result |
|------|--------|
| 15 mandatory rejection scenarios (existing suite, re-run) | all rejected |
| **Mutation fuzz:** 12,303 structural/value mutations (non-identity) of an honest 3-criterion proposal (delete, replace from a hostile value pool, duplicate, swap, reverse, add keys; 1-2 mutations each), with the honest evaluator and an always-SUPPORTED verifier | **0** accepted with a different overall outcome, schema version, ids, hash, criterion set or per-criterion outcome; **0** accepted violating any structural rule (independent oracle: key sets, ordering, vocabularies, reason-code/outcome pairing, evidence-id existence/uniqueness/sorting, `MET` needs non-external evidence, overall consistency) |
| Accepted mutations (immaterial) | 306 = 293 changing only `evidence_ids` + 13 changing only `reason_codes` (all structurally valid and within the closed vocabulary): the by-design weakness AR-06 |
| 300 random validator-side outcome vectors | validator accepts **iff** its own outcomes equal the proposal's (300/300) |
| Verifier veto on any single criterion (3 of 3) | proposal rejected |
| Weak-validator counterfactual (accepts if the overall verdict matches) | accepts a forged proposal with a fabricated citation and an illegal reason code; the real validator rejects it |
| Validator mutates leader value in place | no (deep-equality check) |

The independent harness itself was validated by injecting 16 faults into copies of the contract (validator ignoring outcome mismatch, skipping the verifier, accepting leader errors, writing state before consensus, touching storage in `leader_fn`, removing hash checks, removing authorization, etc.): 15 detected, 1 equivalent mutant (AR-09).

## 8. What majority consensus does and does not give

- GenLayer consensus is **majority-based**, not unanimous. A single validator returning `False` does not necessarily block a transaction; this audit makes no unanimity claim.
- A validator rejection here means: structural flaw, own-evaluation disagreement on any outcome, verifier says UNSUPPORTED, or any exception/leader error.
- Majority acceptance means: the leader's proposal satisfied the above for a majority of validators' independent LLM runs. It does **not** establish factual truth, authenticity of material, identity of authors, accessibility of URLs, independence of validators' underlying models, or absence of shared bias.
- If consensus cannot be reached the transaction does not complete (per the official docs: re-proposal with a new leader, then `UNDETERMINED`); the contract receives no value and persists nothing (executed: 41 simulated consensus failures, state identical).
- Validators' intermediate LLM answers are **not** stored on-chain; the contract stores only the accepted leader result.
- Behaviour of `run_nondet_default` when `validator_fn` returns `False` for a leader *error* (rotation versus immediate failure) is documented for the older API name only: **NOT VERIFIED** for the current API.

## 9. Persistence behaviour

Persistence (lines 1047-1073) happens only after `run_nondet_default` returns; the returned value is re-checked deterministically; the stored `criteria_results_json` is the canonical list of that value; `result_hash` binds ids, package hash, overall outcome and per-criterion tuples; the commitment status flips to `ADJUDICATED` last. Failure at any earlier point leaves no trace (atomicity tested for every public method with 644 hostile calls and a 20,000-step walk).

## 10. Confirmed consensus-related weaknesses

| ID | Severity | Summary |
|----|----------|---------|
| AR-01 | MEDIUM | All criteria are adjudicated, not only the disputed ones (spec discrepancy) |
| AR-02 | MEDIUM | `CHALLENGED` has no exit if adjudication can never complete |
| AR-03 | MEDIUM (impact unverified) | Escaped prompt can reach ~114 KB; provider behaviour at that size unknown |
| AR-06 | INFO | Reason codes / evidence ids verified by LLM, not compared (306/12,303 immaterial acceptances under a permissive verifier) |
| AR-07 | INFO | LLM bias, anchoring, injection persuasion, liveness: untestable here |
| AR-11 | UNVERIFIED | Real-runtime validator behaviour |

## 11. Answer to the most important question

**Can AgentRecall accept and persist an adjudication that materially contradicts the original commitment, acceptance criteria, submitted deliverable, challenge, or evidence because its validator fails to independently verify the complete decision-critical result?**

**No.** From the source (lines 489-581 and 1031-1043) and from 12,303 executed mutations: the validator re-evaluates every criterion from the committed input without seeing the leader's claim, requires identical per-criterion outcomes, re-derives the overall outcome, validates every id, hash, enum and evidence reference, and runs a second independent support check; it does not merely check formatting or the overall verdict. No mutation that changed any decision field, id, hash or criterion set was accepted.

What this answer does **not** cover, and why it matters:
1. It assumes the validators' LLMs judge correctly; correctness of LLM judgement, shared bias and prompt-injection persuasion were not testable (AR-07).
2. `reason_codes` and cited `evidence_ids` are verified by an LLM check, not by equality (AR-06).
3. The result may differ from what the requester expected because *undisputed* criteria are also adjudicated (AR-01).
4. Everything above ran on a stub, not on real consensus (AR-11, AR-12).
