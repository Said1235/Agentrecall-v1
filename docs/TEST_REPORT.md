# AgentRecall V1 - Test report

Generated on 2026-11-24 by `tools/gen_test_report.py` from an actual run. Nothing here is estimated.

## 1. Summary - what is and is not verified

| Level | Status |
|-------|--------|
| Contract implemented | **Yes** (`contracts/agent_recall.py`) |
| Deploy-header check (emulates GenVM's runner-comment read) | **Passes**; the previously delivered file **fails** it (`Extra data`) |
| `genvm-lint check` | **NOT RUN** - linter unavailable in the authoring environment (and it does not detect the header bug) |
| Logic harness (plain CPython + hand-written SDK stub) | **94 / 94 passed** |
| Mutation check of the harness | **19 mutations injected, 19 detected** |
| Direct Mode tests (official fixtures) | **Written (23 functions), NOT EXECUTED** |
| Studio integration tests | **Written (5 functions), NOT EXECUTED** |
| Real deployment, real consensus, real LLM behaviour | **NOT VERIFIED** |

**Tested successfully** = the harness results below: contract logic against a stub that mirrors the
SDK names confirmed in the v0.4 migration guide. **Tested with mocks only** = the same (the LLM is a
deterministic fake; `run_nondet_default` is a stub that runs leader then validator). **Tested in
Studio** = nothing. **Not tested** = anything that depends on the real GenVM, linter or tooling.

**Important limit:** a harness proves logic, not deployability. The first delivery passed 81 harness
tests and still could not be deployed (`invalid_contract runner malformed`). The header, import and
annotation checks added since (section 3: `TestDeployabilityHeader`, `TestKeccakFallback`) reduce
that risk but cannot replace deploying on the real Studio.

## 2. Reproduce

```
python3 -m unittest discover -s tests/harness -v
python3 tools/mutation_check.py
```

## 3. Harness results (executed)

| # | Group | Test | Purpose (from name) | Expected | Actual | Mode |
|---|-------|------|---------------------|----------|--------|------|
| 1 | TestAdjudicationFlow | `test_adjudication_is_permissionless` | adjudication is permissionless | pass | pass | harness (stub SDK) |
| 2 | TestAdjudicationFlow | `test_adjudication_record_is_fully_bound_and_retrievable` | adjudication record is fully bound and retrievable | pass | pass | harness (stub SDK) |
| 3 | TestAdjudicationFlow | `test_evidence_order_is_canonical` | evidence order is canonical | pass | pass | harness (stub SDK) |
| 4 | TestAdjudicationFlow | `test_hash_mismatches_rejected_before_any_llm_call` | hash mismatches rejected before any llm call | pass | pass | harness (stub SDK) |
| 5 | TestAdjudicationFlow | `test_history_is_keyed_and_not_cross_contaminated` | history is keyed and not cross contaminated | pass | pass | harness (stub SDK) |
| 6 | TestAdjudicationFlow | `test_leader_technical_failures_never_persist_and_are_retryable` | leader technical failures never persist and are retryable | pass | pass | harness (stub SDK) |
| 7 | TestAdjudicationFlow | `test_not_adjudicable_before_challenge` | not adjudicable before challenge | pass | pass | harness (stub SDK) |
| 8 | TestAdjudicationFlow | `test_overall_outcome_derivation` | overall outcome derivation | pass | pass | harness (stub SDK) |
| 9 | TestAdjudicationFlow | `test_same_requester_and_executor_many_commitments_have_distinct_ids` | same requester and executor many commitments have distinct ids | pass | pass | harness (stub SDK) |
| 10 | TestAdjudicationFlow | `test_second_adjudication_rejected` | second adjudication rejected | pass | pass | harness (stub SDK) |
| 11 | TestAdjudicationFlow | `test_validator_disagreement_persists_nothing` | validator disagreement persists nothing | pass | pass | harness (stub SDK) |
| 12 | TestCommitmentLifecycle | `test_accept_by_executor_only` | accept by executor only | pass | pass | harness (stub SDK) |
| 13 | TestCommitmentLifecycle | `test_bad_ids_rejected` | bad ids rejected | pass | pass | harness (stub SDK) |
| 14 | TestCommitmentLifecycle | `test_cancel_only_requester_only_while_open` | cancel only requester only while open | pass | pass | harness (stub SDK) |
| 15 | TestCommitmentLifecycle | `test_create_success_and_view` | create success and view | pass | pass | harness (stub SDK) |
| 16 | TestCommitmentLifecycle | `test_duplicate_criteria_ids_rejected` | duplicate criteria ids rejected | pass | pass | harness (stub SDK) |
| 17 | TestCommitmentLifecycle | `test_duplicate_nonce_same_requester_rejected_other_requester_ok` | duplicate nonce same requester rejected other requester ok | pass | pass | harness (stub SDK) |
| 18 | TestCommitmentLifecycle | `test_empty_criteria_rejected` | empty criteria rejected | pass | pass | harness (stub SDK) |
| 19 | TestCommitmentLifecycle | `test_invalid_or_duplicate_kinds_rejected` | invalid or duplicate kinds rejected | pass | pass | harness (stub SDK) |
| 20 | TestCommitmentLifecycle | `test_max_criteria_accepted` | max criteria accepted | pass | pass | harness (stub SDK) |
| 21 | TestCommitmentLifecycle | `test_reject_by_executor_only_and_terminal` | reject by executor only and terminal | pass | pass | harness (stub SDK) |
| 22 | TestCommitmentLifecycle | `test_same_requester_and_executor_rejected` | same requester and executor rejected | pass | pass | harness (stub SDK) |
| 23 | TestCommitmentLifecycle | `test_state_transition_matrix` | state transition matrix | pass | pass | harness (stub SDK) |
| 24 | TestCommitmentLifecycle | `test_too_many_criteria_rejected` | too many criteria rejected | pass | pass | harness (stub SDK) |
| 25 | TestCommitmentLifecycle | `test_unknown_commitment` | unknown commitment | pass | pass | harness (stub SDK) |
| 26 | TestCommitmentLifecycle | `test_zero_executor_rejected` | zero executor rejected | pass | pass | harness (stub SDK) |
| 27 | TestDeployabilityHeader | `test_contract_loads_even_if_sdk_has_no_keccak` | contract loads even if sdk has no keccak | pass | pass | harness (stub SDK) |
| 28 | TestDeployabilityHeader | `test_header_layout_matches_the_studio_example` | header layout matches the studio example | pass | pass | harness (stub SDK) |
| 29 | TestDeployabilityHeader | `test_header_parses_as_exactly_the_runner_json` | header parses as exactly the runner json | pass | pass | harness (stub SDK) |
| 30 | TestDeployabilityHeader | `test_public_methods_use_only_schema_safe_annotations` | public methods use only schema safe annotations | pass | pass | harness (stub SDK) |
| 31 | TestDeployabilityHeader | `test_source_is_plain_ascii` | source is plain ascii | pass | pass | harness (stub SDK) |
| 32 | TestDeployabilityHeader | `test_the_original_bug_is_detected_by_this_check` | the original bug is detected by this check | pass | pass | harness (stub SDK) |
| 33 | TestDeterminismAndBounds | `test_no_nondeterministic_imports_or_float_math_in_contract` | no nondeterministic imports or float math in contract | pass | pass | harness (stub SDK) |
| 34 | TestDeterminismAndBounds | `test_records_are_written_exactly_once_and_never_mutated` | records are written exactly once and never mutated | pass | pass | harness (stub SDK) |
| 35 | TestDeterminismAndBounds | `test_state_writes_only_after_nondet_block` | state writes only after nondet block | pass | pass | harness (stub SDK) |
| 36 | TestHashingAndDomains | `test_domain_separation` | domain separation | pass | pass | harness (stub SDK) |
| 37 | TestHashingAndDomains | `test_encoding_is_injective` | encoding is injective | pass | pass | harness (stub SDK) |
| 38 | TestHashingAndDomains | `test_encoding_rejects_unsupported_types` | encoding rejects unsupported types | pass | pass | harness (stub SDK) |
| 39 | TestHashingAndDomains | `test_hash_changes_when_any_commitment_field_changes` | hash changes when any commitment field changes | pass | pass | harness (stub SDK) |
| 40 | TestHashingAndDomains | `test_ids_depend_on_requester_and_nonce` | ids depend on requester and nonce | pass | pass | harness (stub SDK) |
| 41 | TestHostileInput | `test_boundary_lengths` | boundary lengths | pass | pass | harness (stub SDK) |
| 42 | TestHostileInput | `test_control_characters_rejected` | control characters rejected | pass | pass | harness (stub SDK) |
| 43 | TestHostileInput | `test_deeply_nested_json_rejected_without_parsing` | deeply nested json rejected without parsing | pass | pass | harness (stub SDK) |
| 44 | TestHostileInput | `test_depth_guard_runs_before_json_parsing` | depth guard runs before json parsing | pass | pass | harness (stub SDK) |
| 45 | TestHostileInput | `test_depth_guard_unit_behaviour` | depth guard unit behaviour | pass | pass | harness (stub SDK) |
| 46 | TestHostileInput | `test_evidence_id_namespaces_cannot_collide` | evidence id namespaces cannot collide | pass | pass | harness (stub SDK) |
| 47 | TestHostileInput | `test_injection_text_is_accepted_as_data_but_is_json_escaped_in_the_prompt` | injection text is accepted as data but is json escaped in the prompt | pass | pass | harness (stub SDK) |
| 48 | TestHostileInput | `test_lone_surrogate_rejected` | lone surrogate rejected | pass | pass | harness (stub SDK) |
| 49 | TestHostileInput | `test_oversized_inputs_rejected_before_any_llm_and_quickly` | oversized inputs rejected before any llm and quickly | pass | pass | harness (stub SDK) |
| 50 | TestHostileInput | `test_trivial_and_duplicate_evidence_handling` | trivial and duplicate evidence handling | pass | pass | harness (stub SDK) |
| 51 | TestKeccakFallback | `test_hash_of_largest_material_is_fast_enough_in_plain_python` | hash of largest material is fast enough in plain python | pass | pass | harness (stub SDK) |
| 52 | TestKeccakFallback | `test_permutation_and_sponge_match_hashlib_sha3_for_many_lengths` | permutation and sponge match hashlib sha3 for many lengths | pass | pass | harness (stub SDK) |
| 53 | TestKeccakFallback | `test_published_keccak256_vectors` | published keccak256 vectors | pass | pass | harness (stub SDK) |
| 54 | TestKeccakFallback | `test_sdk_failure_at_runtime_falls_back_to_pure` | sdk failure at runtime falls back to pure | pass | pass | harness (stub SDK) |
| 55 | TestLlmOutputCoercion | `test_contract_calls_exec_prompt_in_plain_text_mode` | contract calls exec prompt in plain text mode | pass | pass | harness (stub SDK) |
| 56 | TestLlmOutputCoercion | `test_fenced_json_text_is_accepted_like_in_the_studio_example` | fenced json text is accepted like in the studio example | pass | pass | harness (stub SDK) |
| 57 | TestLlmOutputCoercion | `test_json_text_and_parsed_json_are_equivalent` | json text and parsed json are equivalent | pass | pass | harness (stub SDK) |
| 58 | TestLlmOutputCoercion | `test_non_json_python_values_still_rejected_by_shape_validation` | non json python values still rejected by shape validation | pass | pass | harness (stub SDK) |
| 59 | TestLlmOutputCoercion | `test_oversized_or_deep_or_invalid_text_rejected` | oversized or deep or invalid text rejected | pass | pass | harness (stub SDK) |
| 60 | TestSmokeContract | `test_smoke_header_is_valid_and_matches_main_contract` | smoke header is valid and matches main contract | pass | pass | harness (stub SDK) |
| 61 | TestSmokeContract | `test_smoke_logic_runs` | smoke logic runs | pass | pass | harness (stub SDK) |
| 62 | TestSubmissionAndChallenge | `test_challenge_rules` | challenge rules | pass | pass | harness (stub SDK) |
| 63 | TestSubmissionAndChallenge | `test_close_uncontested_is_not_a_verdict` | close uncontested is not a verdict | pass | pass | harness (stub SDK) |
| 64 | TestSubmissionAndChallenge | `test_evidence_count_boundary` | evidence count boundary | pass | pass | harness (stub SDK) |
| 65 | TestSubmissionAndChallenge | `test_evidence_kind_must_be_accepted_by_commitment` | evidence kind must be accepted by commitment | pass | pass | harness (stub SDK) |
| 66 | TestSubmissionAndChallenge | `test_silence_leaves_commitment_submitted` | silence leaves commitment submitted | pass | pass | harness (stub SDK) |
| 67 | TestSubmissionAndChallenge | `test_submit_authorization_and_state` | submit authorization and state | pass | pass | harness (stub SDK) |
| 68 | TestSubmissionAndChallenge | `test_submit_rejects_bad_material` | submit rejects bad material | pass | pass | harness (stub SDK) |
| 69 | TestSubmissionAndChallenge | `test_submit_success` | submit success | pass | pass | harness (stub SDK) |
| 70 | TestValidatorRule | `test_01_leader_fulfilled_validator_not_fulfilled` | 01 leader fulfilled validator not fulfilled | pass | pass | harness (stub SDK) |
| 71 | TestValidatorRule | `test_02_single_criterion_disagreement` | 02 single criterion disagreement | pass | pass | harness (stub SDK) |
| 72 | TestValidatorRule | `test_03_omitted_criterion` | 03 omitted criterion | pass | pass | harness (stub SDK) |
| 73 | TestValidatorRule | `test_04_invented_criterion` | 04 invented criterion | pass | pass | harness (stub SDK) |
| 74 | TestValidatorRule | `test_05_omitted_finding_leader_downgrades_to_indeterminate` | 05 omitted finding leader downgrades to indeterminate | pass | pass | harness (stub SDK) |
| 75 | TestValidatorRule | `test_06_unsupported_finding_rejected_by_verifier` | 06 unsupported finding rejected by verifier | pass | pass | harness (stub SDK) |
| 76 | TestValidatorRule | `test_07_nonexistent_evidence_reference` | 07 nonexistent evidence reference | pass | pass | harness (stub SDK) |
| 77 | TestValidatorRule | `test_08_changed_evidence_package_hash` | 08 changed evidence package hash | pass | pass | harness (stub SDK) |
| 78 | TestValidatorRule | `test_09_changed_submission_id_and_other_ids` | 09 changed submission id and other ids | pass | pass | harness (stub SDK) |
| 79 | TestValidatorRule | `test_10_positive_verdict_with_contradictory_criteria` | 10 positive verdict with contradictory criteria | pass | pass | harness (stub SDK) |
| 80 | TestValidatorRule | `test_10b_negative_verdict_with_all_met` | 10b negative verdict with all met | pass | pass | harness (stub SDK) |
| 81 | TestValidatorRule | `test_11_malformed_structured_data` | 11 malformed structured data | pass | pass | harness (stub SDK) |
| 82 | TestValidatorRule | `test_12_invalid_schema_version` | 12 invalid schema version | pass | pass | harness (stub SDK) |
| 83 | TestValidatorRule | `test_13_unsupported_reason_code` | 13 unsupported reason code | pass | pass | harness (stub SDK) |
| 84 | TestValidatorRule | `test_14_validator_cannot_evaluate` | 14 validator cannot evaluate | pass | pass | harness (stub SDK) |
| 85 | TestValidatorRule | `test_15_validator_technical_error_never_becomes_agreement` | 15 validator technical error never becomes agreement | pass | pass | harness (stub SDK) |
| 86 | TestValidatorRule | `test_different_reason_codes_and_evidence_with_same_outcome_are_not_exact_matched` | different reason codes and evidence with same outcome are not exact matched | pass | pass | harness (stub SDK) |
| 87 | TestValidatorRule | `test_ghost_evidence_rejected_for_every_outcome_type` | ghost evidence rejected for every outcome type | pass | pass | harness (stub SDK) |
| 88 | TestValidatorRule | `test_honest_proposal_accepted` | honest proposal accepted | pass | pass | harness (stub SDK) |
| 89 | TestValidatorRule | `test_leader_error_result_is_never_accepted` | leader error result is never accepted | pass | pass | harness (stub SDK) |
| 90 | TestValidatorRule | `test_met_cannot_rest_only_on_external_reference` | met cannot rest only on external reference | pass | pass | harness (stub SDK) |
| 91 | TestValidatorRule | `test_met_with_no_evidence_rejected` | met with no evidence rejected | pass | pass | harness (stub SDK) |
| 92 | TestValidatorRule | `test_naive_status_only_validator_would_accept_a_forgery_the_real_one_rejects` | naive status only validator would accept a forgery the real one rejects | pass | pass | harness (stub SDK) |
| 93 | TestValidatorRule | `test_non_canonical_ordering_rejected` | non canonical ordering rejected | pass | pass | harness (stub SDK) |
| 94 | TestValidatorRule | `test_prose_only_differences_cannot_exist_in_the_proposal` | prose only differences cannot exist in the proposal | pass | pass | harness (stub SDK) |

## 4. Mutation check (executed)

Each defect is applied to a temporary copy of the contract; the suite must fail. The baseline is asserted green first.

| Result | Injected defect |
|--------|-----------------|
| KILLED | comment glued under runner line (the real deploy bug) |
| KILLED | address-typed public argument |
| KILLED | decorated __init__ (forbidden in v0.4) |
| KILLED | json response_format reintroduced |
| KILLED | keccak fallback broken (wrong padding) |
| KILLED | validator skips claim verification |
| KILLED | validator skips independent outcome comparison |
| KILLED | validator accepts leader errors |
| KILLED | no content hash check at adjudication |
| KILLED | MET may rest on external reference |
| KILLED | overall not derived consistently |
| KILLED | evidence ids not checked against package |
| KILLED | ids not compared (package hash) |
| KILLED | anyone can accept |
| KILLED | challenge allowed in wrong state |
| KILLED | no domain separation |
| KILLED | duplicate evidence content allowed |
| KILLED | no depth guard |
| KILLED | persist even if status check skipped |

## 5. Not executed

### 5.1 Direct Mode (`tests/direct/test_agent_recall.py`)

`pytest tests/direct/ -v` with genlayer-test 0.30.0. Functions (several parametrized):

- `test_create_commitment_and_exact_lookup`
- `test_create_commitment_rejects_invalid_input`
- `test_create_rejects_zero_and_self_executor`
- `test_duplicate_nonce_rejected_per_requester`
- `test_authorization_on_open_commitment`
- `test_accept_reject_cancel_paths_and_terminal_states`
- `test_unknown_commitment`
- `test_submission_rules`
- `test_challenge_rules`
- `test_close_uncontested_is_not_a_positive_verdict`
- `test_silence_keeps_commitment_submitted`
- `test_adjudication_outcomes_and_binding`
- `test_adjudication_is_permissionless`
- `test_hash_mismatch_rejected_before_any_llm_call`
- `test_second_adjudication_and_early_adjudication_rejected`
- `test_malformed_llm_output_never_persists_and_is_retryable`
- `test_history_is_keyed_and_not_cross_contaminated`
- `test_validator_accepts_the_honest_proposal`
- `test_validator_rejects_forged_leader`
- `test_14_validator_without_llm_response_rejects`
- `test_15_validator_with_malformed_llm_output_rejects`
- `test_prompt_injection_is_data_not_instruction`
- `test_control_characters_and_oversize_rejected`

### 5.2 Studio (`tests/integration/test_agent_recall_studio.py`)

`gltest tests/integration/ -v -s` against a Studio you are authorized to use. Fees apply (Studio v0.123). Functions:

- `test_full_lifecycle_with_real_consensus`
- `test_unauthorized_actions_fail_and_do_not_change_state`
- `test_uncontested_path_is_not_a_verdict`
- `test_failed_adjudication_leaves_state_unchanged`
- `test_multiple_commitments_are_independently_retrievable`

### 5.3 Checks nobody has run yet
1. Deploying the file on the real Studio and reading the schema it produces
2. `genvm-lint check contracts/agent_recall.py --json`
3. Real validator behaviour when `validator_fn` returns `False` for a leader `[LLM_ERROR]`
4. Real LLM text output (fenced JSON, extra prose) and the contract's parsing of it
5. Consensus rotation, `UNDETERMINED`, finality, appeals, fees for `adjudicate`
6. Storage construction of dataclasses with `Address` / `u32` fields; `gl.message.raw["datetime"]`
7. Behaviour with the largest allowed package (~37 KB of prompt data)
8. Whether the SDK's `Keccak256` is importable on the real runner (the contract works either way)
