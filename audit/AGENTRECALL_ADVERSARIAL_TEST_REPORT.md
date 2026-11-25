# AgentRecall V1 - Adversarial test report

Audited commit `4c50da760bdd997eba9e0f6e954efae49e83f907`. Contract SHA-256 `64575c671b33ebb5d9ae0972a90ab296e7dbbe1ab3b8bc0f2984d3a0914b5e9d`, unchanged before and after the audit. Raw outputs are in `audit/evidence/`.

## 1. Environment and execution mode

| Item | Value |
|------|-------|
| Interpreter | Python 3.12.3, standard library only (+ `cloudpickle 3.1.2` for one test) |
| SDK | **hand-written dev stub** (`tests/harness/stub/genlayer`): implements only the names the contract uses; `Keccak256` is SHA3-256; `run_nondet_default` runs the leader then the validator in-process; storage is a Python dict |
| LLM | deterministic fakes (callables returning chosen JSON); **no real LLM** |
| Consensus | simulated (stub raises `ConsensusDisagreement` when `validator_fn` returns `False`); **no real validators, no appeals, no finality** |
| Not available | `genvm-lint`, `genlayer` CLI, `gltest`, `pytest`, Docker, Studio/Localnet, network for the shell |

**Mocked versus real:** everything here is mocked/simulated. These results validate the contract's own logic. They say nothing about the real GenVM, SDK, storage, LLMs or consensus.

## 2. Exact commands and results

| # | Command (run from the repository root) | Exit | Result | Output file |
|---|-----------------------------------------|------|--------|-------------|
| 0 | environment inspection (see file) | 0 | no GenLayer tooling installed | `evidence/00_environment.txt` |
| 1 | `python3 -m unittest discover -s tests/harness -v` (the author's existing suite, unmodified) | 0 | 94 tests, OK | `evidence/01_existing_tests.txt` |
| 2 | `python3 tools/mutation_check.py` (the author's mutation check) | 0 | 19 mutations, 19 detected | `evidence/02_existing_mutations.txt` |
| 3 | `python3 audit/harness/audit_harness.py -v` (independent audit harness) | 0 | **34 tests, OK** | `evidence/03_audit_harness_run.txt`, `evidence/stats.json` |
| 4 | `python3 audit/harness/mutant_check.py` (does the audit harness detect injected faults?) | 0 | baseline passes; **15 of 16** faults detected; 1 equivalent mutant (AR-09) | `evidence/04_audit_harness_mutants.txt` |

Not run, and why: `genvm-lint check` / `genvm-lint schema` (tool unavailable), `pytest tests/direct/` (pytest and genlayer-test unavailable), `gltest tests/integration/` (no Studio/Docker), any test with a real LLM.

## 3. Key measurements (from `evidence/stats.json`)

| Measurement | Value |
|-------------|-------|
| Hostile-argument calls (13 public methods x each parameter x 23 hostile values) | 644 |
|   ... that raised anything other than a controlled `UserError` | 0 |
|   ... where a write accepted a non-string argument | 0 |
| Random-walk steps vs. independent reference model | 20000 |
|   successes / rejections / simulated consensus failures | 1606 / 18353 / 41 |
| Leader-proposal mutations tested | 12303 |
|   accepted with a **material** change | 0 |
|   accepted with a structural violation | 0 |
|   accepted, immaterial (reason codes / evidence ids only) | 306  (evidence_ids: 293, reason_codes: 13) |
| Validator-side outcome vectors checked (accepts iff equal) | 300 |
| Byte-variant adjudications rejected as HASH_MISMATCH | 9 of 9 |
| Closure free variables (leader / validator) | ['ctx'] / ['ctx'] |
| cloudpickle round-trip of both closures | leader_fn and validator_fn pickled/unpickled and executed (cloudpickle 3.1.2) |
| Storage writes inside `adjudicate` (line, target) | [[1057, 'self.adjudications[aid]'], [1073, 'self.commitment_status[commitment_id]']] |
| Max valid prompt, ASCII (evaluator / verifier bytes) | 40448 / 41448 |
| Max valid prompt, astral characters (evaluator / verifier bytes) | 113788 / 114788 |
| Astral inflation factor (evaluator) | 2.81 |
| Slowest 300 KB rejection (seconds, CPython) | 0.0002 |
| Pure-Python Keccak, 32 KB (seconds, CPython) | 0.0842 |
| Docs claiming a ~37 KB largest prompt | docs/DEPLOYMENT_READINESS.md:97, docs/SECURITY_AUDIT.md:29, docs/TEST_REPORT.md:207 |

## 4. Test matrix versus the audit prompt (section 17)

Legend: **S** = executed in the audit harness (stub); **E** = executed in the author's existing suite (stub); **-** = not applicable (reason given); **NOT RUN** = needs real tooling.

| Area | Item | Status | Where |
|------|------|--------|-------|
| A Lifecycle | valid creation; identical requester/executor; invalid executor (zero, malformed, non-string) | S, E | A1, A2, existing `TestCommitmentLifecycle` |
| | "invalid requester" | - the requester is the transaction sender; there is no requester argument | |
| | accept / reject / cancel while OPEN; cancel after ACCEPTED; submit before acceptance, after rejection, after cancellation; duplicate accept/submit | S, E | A5 matrix, A6 replay + terminal states, A2 walk |
| | permanent ACCEPTED | documented (AR-13); executed implicitly in the walk | |
| B Submission/challenge | valid submission; empty submission; wrong commitment id | S, E | A1 (hostile values incl. `""`, wrong ids -> NOT_FOUND) |
| | wrong submission id | - submission ids are derived from the commitment id; views reject unknown ids (A1) | |
| | challenge by requester / executor / unrelated; duplicate; after UNCONTESTED; unknown or duplicated criterion ids; challenge without evidence | S, E | A5, A6, existing `test_challenge_rules` |
| | challenge against another commitment | S | A2 walk (random targets), A6 isolation |
| C Adjudication | valid challenge + valid evidence; outcomes MET / NOT_MET / INDETERMINATE | S, E | A3 honest proposal carries all three outcomes; A6 |
| | incorrect leader verdict; missing / duplicate / unknown criterion; invalid reason code; invalid evidence id; unsupported conclusion; contradictory outcomes and overall; correct status with wrong details | S | A3 (12,303 mutations + 300 outcome vectors + verifier veto + weak-validator counterfactual) |
| | evidence from another submission | S | A3 (ids outside the package rejected) + A4 cross-record |
| | validator rejects / accepts; leader-validator disagreement; leader error; validator error; undetermined consensus; retry; duplicate adjudication | S, E | A2 (41 simulated failures), A6, existing consensus tests |
| D Evidence | correct content; modified; wrong hash; Unicode (NFC/NFD, homoglyph, zero-width); line endings; truncated; empty; duplicate ids; other commitment / submission; missing original; different manifest | S | A4 |
| | "wrong encoding" | partially: content is `str` (no byte encodings to choose); only text variants testable | |
| E Authorization | requester-only / executor-only / permissionless; unauthorized transitions; relayer substitution and repetition | S | A5 |
| F Prompt injection | fake system text, delimiters, malicious criteria/evidence/commitment/challenge, JSON/Unicode tricks | E (6 payloads, stub) | existing `TestHostileInput`; **real LLM susceptibility NOT RUN** |
| | output manipulation, invented evidence, vocabulary change | S | A3 (strict shape + oracle) |
| G Resources | oversized commitment / submission / challenge / criteria / evidence; max allowed; just above max | S, E | A8 (eight 300 KB probes), existing boundary tests |
| | large structured payloads, deep nesting | S, E | A4 JSON edge cases, existing depth tests |
| H Concurrency | multiple commitments per requester / executor; result retrieval after newer records; retry | S | A6 (8 commitments), A2 |
| | concurrent challenge attempts; multiple pending adjudications | partially: sequential only; real concurrency semantics **NOT RUN** | |
| I Official tools | Direct Mode with `check_pickling`, `mock_llm`, `run_validator`; Localnet integration | **NOT RUN** | `tests/direct`, `tests/integration` exist but were never executed |

## 5. Defects found in the audit's own tooling (and fixed)

The audit harness itself had bugs. They were found and corrected; none was a contract defect, and the contract file was never edited.
1. Max-input measurement cited evidence ids that did not exist in that scenario; the contract correctly rejected them.
2. The reference model expected a failure for an operation that carries no corrupted argument.
3. The reference model gave consensus failure precedence over a hash mismatch; the contract correctly checks hashes first.
4. The meta-check (`mutant_check.py`) exposed a **gap in the audit's own oracle**: it did not independently assert that cited evidence ids exist. An independent structural oracle was added; the corresponding fault is now detected.

## 6. Reproduction

```
git checkout 4c50da7
python3 -m unittest discover -s tests/harness -v
python3 tools/mutation_check.py
python3 audit/harness/audit_harness.py -v
python3 audit/harness/mutant_check.py
```
(The `audit/` directory is added in the commit after the audited one; check out the latest commit to obtain it, with `contracts/agent_recall.py` byte-identical.)

## 7. Unverified properties (not claimed)

Real consensus, appeals, finality and rotation; real LLM judgement, anchoring and injection resistance; real storage serialization and dataclass construction; real schema generation and linter acceptance; real transaction ordering; fee-aware deploy/write; provider behaviour for ~114 KB prompts.

## Appendix A. Audit harness inventory (generated from `audit/harness/audit_harness.py`)

**`A1_TypeConfusionAndAtomicity`** - Every public method with hostile argument values: only controlled UserErrors, and a failed
- `test_hostile_arguments`

**`A2_ModelBasedRandomWalk`** - Independent reference model of the lifecycle; random operations by random actors against
- `test_random_walks`

**`A3_ValidatorMutationFuzz`** - Mutation-fuzz the leader proposal. Any ACCEPTED mutation must be immaterial (identical
- `test_mutation_fuzz`
- `test_validator_rejects_whenever_its_own_outcome_differs`
- `test_verifier_veto_on_any_single_criterion`
- `test_stored_result_equals_accepted_proposal`

**`A4_EvidenceIntegrity`** - FINDING input: duplicate object keys are not rejected. Last key wins (CPython json); the hash
- `test_byte_exactness_variants_all_rejected`
- `test_evidence_manifest_variants_rejected`
- `test_cross_record_substitution`
- `test_identical_bytes_in_two_commitments_stay_isolated`
- `test_json_edge_cases`
- `test_duplicate_json_keys_last_wins_is_deterministic`
- `test_reserved_delivery_id_cannot_be_forged`

**`A5_AuthorizationAndRelayer`** - 
- `test_actor_by_operation_matrix`
- `test_relayer_has_no_authority_over_inputs_or_verdict`
- `test_no_adjudicate_without_challenge_in_any_state`
- `test_uncontested_cannot_be_challenged_or_adjudicated`

**`A6_RecordIdentifiersAndReplay`** - Documents FINDING (permanent CHALLENGED if adjudication can never complete).
- `test_many_commitments_same_wallets_exact_lookup`
- `test_same_nonce_different_requesters_and_executors`
- `test_every_successful_write_is_not_replayable`
- `test_terminal_states_are_closed`
- `test_no_exit_from_challenged_except_adjudicate`

**`A7_ConsensusStructure`** - Lists every `for` loop in the module so a human can review iteration sources; automatically
- `test_closures_capture_only_plain_data`
- `test_cloudpickle_roundtrip_of_closures`
- `test_no_storage_access_or_writes_inside_or_before_nondet_block`
- `test_deterministic_code_has_no_set_or_dict_iteration_order_dependence`
- `test_error_messages_are_deterministic_strings`
- `test_weak_validator_counterfactual_is_rejected_by_the_real_one`

**`A8_PromptAndResourceBounds`** - 
- `test_maximum_valid_input_prompt_sizes_ascii_vs_astral`
- `test_oversized_inputs_are_rejected_fast_and_without_llm`
- `test_pure_python_keccak_cost_at_maximum_hashed_volume`

**`A9_SdkCompatibilityStatic`** - Static comparison against the v0.4 migration guide items named in the audit prompt.
- `test_checklist`

**`A10_SpecDiscrepancies`** - Binding spec 1.3 step 6: 'Adjudication evaluates the DISPUTED criteria'. Implementation: every committed
- `test_all_criteria_are_evaluated_not_only_disputed_ones`

**`A11_DocumentationDiscrepancies`** - 
- `test_documented_prompt_size_vs_measured`
