# AgentRecall V1 - Adversarial security audit

Method: threat enumeration (`THREAT_MODEL.md`), then attack-driven tests, then **mutation
testing** of the test-suite itself: 19 deliberate defects (including the real deploy-header bug, a typed public
argument, a decorated `__init__`, a re-introduced JSON mode and a broken Keccak padding) were
injected into a copy of the contract and the logic harness had to fail for each. Scope: the contract source and the logic
harness only. The real GenVM, real LLMs, the linter and real consensus were **not** available;
conclusions about those are explicitly marked "unverified".

## 1. Failure-injection matrix

"Test" = test in `tests/harness/test_logic.py` (executed, stub SDK). The same scenarios are in
`tests/direct/` (not executed) and partly in `tests/integration/` (not executed).

| # | Attack / failure | Entry point | Expected behaviour | State that must stay unchanged | Test | Residual risk |
|---|------------------|-------------|--------------------|-------------------------------|------|---------------|
| 1 | Act as another party (accept / reject / cancel / submit / challenge / close) | all writes | `[EXPECTED] UNAUTHORIZED` | commitment status | `test_accept_by_executor_only`, `test_reject_*`, `test_cancel_*`, `test_submit_authorization_and_state`, `test_challenge_rules`, `test_close_uncontested_*` | none known |
| 2 | Fake delivery by third party | `submit_delivery` | `UNAUTHORIZED` | status, submissions | `test_submit_authorization_and_state` | none |
| 3 | Change criteria after acceptance | none exists | no code path | commitment record | `test_records_are_written_exactly_once_and_never_mutated` (static) | none |
| 4 | Reuse a commitment id | `create_commitment` | `ALREADY_EXISTS`; another requester gets a different id | existing record | `test_duplicate_nonce_*` | none |
| 5 | Replay a challenge / second submission | `create_challenge`, `submit_delivery` | `INVALID_STATE` | status | `test_challenge_rules`, `test_submit_*` | none |
| 6 | Substitute evidence at adjudication | `adjudicate` | `HASH_MISMATCH` before any LLM call | status `CHALLENGED`, no adjudication | `test_hash_mismatches_rejected_before_any_llm_call` (9 variants) | none |
| 7 | Confuse record lookup / cross-contaminate | views, `adjudicate` | exact-key lookups; independent records | other records | `test_history_is_keyed_and_not_cross_contaminated` | none |
| 8 | Conflicting transactions on one commitment | writes | the first to execute wins; the second fails `INVALID_STATE` | status of winner | transition matrix | ordering across accounts is decided by the network |
| 9 | Stale state / double adjudication | `adjudicate` | `INVALID_STATE`; `ALREADY_EXISTS` guard | existing adjudication | `test_second_adjudication_rejected` | none |
| 10 | Validator approves an incomplete / contradictory result | `validator_fn` | `False` for all 15 mandatory scenarios plus 5 extra | no adjudication | `TestValidatorRule` (25 tests) | see 11 |
| 11 | Leader picks a plausible wrong reason code or citation for a correct outcome | `validator_fn` | passes if verifier judges it supported (decision E9) | - | `test_different_reason_codes_...` documents the behaviour | **accepted residual risk** |
| 12 | Prompt injection (delivery, criteria, evidence, challenge; fake roles; JSON/delimiter breaks; bidi/confusables) | all text inputs | stored as data; escaped on one line; instructions only in contract text; output reduced to enums/ids | - | `test_injection_text_is_accepted_as_data_but_is_json_escaped_in_the_prompt` (6 payloads) | an LLM may still be persuaded by text inside a JSON string; **unverified against real LLMs** |
| 13 | Unbounded computation / memory | all inputs | `INPUT_TOO_LARGE` / `INVALID_INPUT` before parsing or LLM | - | `test_oversized_inputs_*` (300 KB), `test_deeply_nested_json_*`, `test_boundary_lengths` | LLM provider context limits at the maximum package (~37 KB) are unknown |
| 14 | Malformed / extra-key / invalid-enum LLM output | leader & validator | rejected; leader raises `[LLM_ERROR]`; validator `False` | status, adjudications | `test_leader_technical_failures_*`, `TestLlmOutputCoercion` | none |
| 15 | Technical failure presented as a verdict | `adjudicate` | nothing persisted; retry possible | status `CHALLENGED` | `test_leader_technical_failures_*`, `test_15_*`, `test_validator_disagreement_persists_nothing` | none |
| 16 | Contradictory stored fields | all | one status source; overall outcome derived | - | `test_records_are_written_exactly_once_*`, `test_10_*`, `test_10b_*` | none |
| 17 | Later transaction overwrites earlier record | writes | records written once; ids unique | earlier records | `test_records_are_written_exactly_once_*` | none |
| 18 | Finality assumptions: an `ACCEPTED` result is later changed by appeal | frontend | frontends show finality state | - | documentation only | see `FRONTEND_INTEGRATION.md` section F |
| 19 | Duplicate corroboration / trivial or irrelevant evidence | `submit_delivery`, `create_challenge` | identical `(kind, content)` rejected; whitespace-only rejected; irrelevance judged by verifier | - | `test_trivial_and_duplicate_evidence_handling` | zero-width-only text is "non-empty" and relies on the verifier |
| 20 | MET resting only on an unverified URL | validator | rejected deterministically | - | `test_met_cannot_rest_only_on_external_reference` | none |
| 21 | Control characters / lone surrogates | text inputs | `INVALID_INPUT` | - | `test_control_characters_rejected`, `test_lone_surrogate_rejected` | none |
| 22 | Leader forces repeated rotation (liveness) | `adjudicate` | no state change; eventually `UNDETERMINED` | status | `test_validator_disagreement_persists_nothing` | **accepted residual risk** |
| 23 | Early adjudication relayed by the counterparty | `adjudicate` | allowed by decision B3; requires the exact original material | - | `test_adjudication_is_permissionless` | by design |

## 2. Mandatory regression lessons (from the specification)

| Lesson | How it is prevented |
|--------|---------------------|
| Incomplete validator verification | Per-criterion outcome equality, full structural check, verifier. Tests 01-13, 16, 17. |
| Score tolerance | No score or numeric field exists. |
| Missing source commitment | `evidence_package_hash` binds commitment, submission and challenge; verified before LLM. |
| Incorrect record association | Derived ids; every adjudication stores commitment, submission, challenge ids and all three hashes. |
| Shared latest-result overwrite | None exists; keyed maps only. |
| Prompt injection | See row 12. |
| Irrelevant excerpts | Verifier call + deterministic citation checks. Residual: row 11. |
| Duplicate corroboration | Row 19. |
| Temporary failures | Row 15. |
| Premature resolution | Persistence only after `run_nondet_default` returns; static test. |

## 3. Findings from this review

| # | Severity | Finding | Status |
|---|----------|---------|--------|
| F1 | Medium (test quality) | Mutation testing showed the suite did not prove citation checks for `NOT_MET`/`INDETERMINATE` (a `KeyError` masked the gap for `MET`), and the JSON depth test passed for the wrong reason. | **Fixed**; new tests added; all 14 original mutations now fail the suite (19/19 including the later deployability mutations). |
| F2 | Medium (product) | Adjudication evaluates **all** criteria, so a challenge on `C1` can yield `NOT_MET` for undisputed `C2` (decision E12). | **Open - needs owner confirmation.** |
| F3 | Medium (unverified runtime) | Several runtime behaviours could not be verified here: see section 4. | **Open - verify on first real run.** |
| F4 | Low | Matching of outcomes only (E9) lets a plausible-but-suboptimal reason code or citation pass if supported. | Accepted, documented. |
| F5 | Low | `created_at` format and `Keccak256(...).digest()` return type are unverified. | Open. |
| F6 | Info | All submitted material is public in calldata, twice. | Documented limitation. |
| F7 | **Critical (deployability)** | The first delivered file could not be deployed: `# { "Depends": ... }` was followed by more `#` lines, which GenVM parses as part of the runner JSON (`invalid_contract runner malformed`, shown as "Could not load contract schema"). Neither the linter nor Direct Mode tests detect it, so the earlier audit and harness missed it. | **Fixed.** New header regression tests; the old file fails them, the new one passes. Lesson: a harness proves logic, never deployability. |
| F8 | Medium (deployability) | Unverified assumptions that could also break schema loading: `Keccak256` import path, `Address`-typed arguments, JSON-mode `exec_prompt`. | **Mitigated**: import chain + verified pure-Python fallback; `str` arguments; text mode (decisions E20, E21, E23). |

## 4. What this audit does not establish

- Real-GenVM behaviour: closure serialization of `leader_fn`/`validator_fn`; storage dataclass
  construction with `Address` and `u32` fields; `TreeMap` value assignment; `gl.message.raw["datetime"]`;
  text-mode `exec_prompt` output on real validators; behaviour when `validator_fn` returns
  `False` for a leader error under `run_nondet_default`; the behaviour of the real Studio beyond
  the header (the `kzybg95x...` runner is the one announced for new contracts on 23 Nov 2026).
- Linter acceptance (`genvm-lint check`) and schema generation (`genvm-lint schema`), including
  that `list[...]`-free argument types and `dict[str, typing.Any]` view returns load correctly.
- Real LLM behaviour under injection; real multi-validator consensus; finality and appeals.
- The SDK's own `Keccak256` (the harness stub uses SHA3-256; the contract's pure-Python
  fallback *is* verified against published Keccak-256 vectors).
