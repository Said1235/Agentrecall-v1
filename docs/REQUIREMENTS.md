# AgentRecall V1 - Requirements and invariants

## 1. Purpose

Record bilateral commitments between exactly two participants (requester, executor) and, when
the requester disputes a delivery, produce an immutable adjudication record through GenLayer
validator consensus. The only consequence is the persistent record. No funds, tokens,
reputation or penalties are touched.

## 2. Functional requirements

| ID | Requirement | Method |
|----|-------------|--------|
| F1 | Create a commitment with immutable, uniquely identified, atomic acceptance criteria | `create_commitment` |
| F2 | Executor accepts or rejects; requester may cancel only while `OPEN` | `accept_commitment`, `reject_commitment`, `cancel_commitment` |
| F3 | Executor submits one delivery with evidence; only commitments are stored | `submit_delivery` |
| F4 | Requester challenges the submission, naming disputed criteria | `create_challenge` |
| F5 | Requester may explicitly close an unchallenged submission (not a verdict) | `close_uncontested` |
| F6 | Anyone may relay adjudication, re-supplying the original material | `adjudicate` |
| F7 | Exact retrieval of commitment, submission, challenge, adjudication | `get_*` |
| F8 | Clients can derive ids and read limits without guessing | `compute_commitment_id`, `get_limits` |

## 3. Non-functional requirements

No constructor arguments or secrets; no external services; bounded inputs and bounded loops;
fail-closed consensus; English-only code and documentation; no public deployment.

## 4. Invariants

"Enforced by" names the mechanism; "Evidence" names the tests that exercise it (all in
`tests/harness/test_logic.py` unless stated; the same scenarios exist, unexecuted, in
`tests/direct/`).

### Identity
| ID | Invariant | Enforced by | Evidence |
|----|-----------|-------------|----------|
| I1 | A commitment has exactly one requester and one executor | `create_commitment` fixes both at creation | `test_create_success_and_view` |
| I2 | Requester != executor; executor != zero address | explicit checks | `test_same_requester_and_executor_rejected`, `test_zero_executor_rejected` |
| I3 | Every child record belongs to exactly one parent | child ids are hashes of the parent id; child stores parent id | `test_adjudication_record_is_fully_bound_and_retrievable` |

### Immutability
| ID | Invariant | Enforced by | Evidence |
|----|-----------|-------------|----------|
| M1 | Accepted criteria cannot change | no method mutates a `Commitment`; only `commitment_status` is mutable | `test_records_are_written_exactly_once_and_never_mutated` (static) |
| M2 | Submitted commitments cannot be replaced | status gate `ACCEPTED -> SUBMITTED` once | `test_submit_authorization_and_state` |
| M3 | A completed adjudication cannot be overwritten | status gate + `ALREADY_EXISTS` check | `test_second_adjudication_rejected` |

### Authorization
| ID | Invariant | Evidence |
|----|-----------|----------|
| A1 | Only the executor accepts / rejects / submits | `test_accept_by_executor_only`, `test_reject_by_executor_only_and_terminal`, `test_submit_authorization_and_state` |
| A2 | Only the requester cancels / challenges / closes uncontested | `test_cancel_only_requester_only_while_open`, `test_challenge_rules`, `test_close_uncontested_is_not_a_verdict` |
| A3 | Adjudication is permissionless and grants no authority to the relayer | `test_adjudication_is_permissionless` |

### Evidence
| ID | Invariant | Enforced by | Evidence |
|----|-----------|-------------|----------|
| V1 | Evaluated material equals committed material | recomputed hashes compared before any LLM call | `test_hash_mismatches_rejected_before_any_llm_call` |
| V2 | Every referenced evidence id exists | `_canonical_results` | `test_07_*`, `test_ghost_evidence_rejected_for_every_outcome_type` |
| V3 | Evidence ids are unique within a manifest and namespaces cannot collide | `_normalize_evidence`, `_build_package` | `test_submit_rejects_bad_material`, `test_evidence_id_namespaces_cannot_collide` |
| V4 | No model-generated text is ever stored or accepted as evidence | proposal has no free text; only ids/enums | `test_prose_only_differences_cannot_exist_in_the_proposal` |

### Consensus
| ID | Invariant | Evidence |
|----|-----------|----------|
| C1 | Validator receives the leader's actual result and checks its type first | `test_leader_error_result_is_never_accepted` |
| C2 | Validator independently evaluates the same committed input | `test_01_*`, `test_02_*`, `test_05_*` |
| C3 | Every material field is checked; contradictory or incomplete proposals cannot pass | `test_03..test_13`, `test_non_canonical_ordering_rejected` |
| C4 | Invalid / unverifiable output is never accepted | `test_14_*`, `test_15_*`, `test_leader_technical_failures_never_persist_and_are_retryable` |

### State
| ID | Invariant | Evidence |
|----|-----------|----------|
| S1 | No invalid transition is possible | `test_state_transition_matrix` (8 x 7 pairs) |
| S2 | A technical error cannot create a business verdict | `test_leader_technical_failures_*`, `test_validator_disagreement_persists_nothing` |
| S3 | An unchallenged submission is never represented as fulfilled | `test_close_uncontested_is_not_a_verdict`, `test_silence_leaves_commitment_submitted` |
| S4 | State is written only after consensus returns | `test_state_writes_only_after_nondet_block` (static) |

### History
| ID | Invariant | Evidence |
|----|-----------|----------|
| H1 | Records are keyed and independently retrievable | `test_history_is_keyed_and_not_cross_contaminated` |
| H2 | New records cannot overwrite unrelated records | `test_duplicate_nonce_same_requester_rejected_other_requester_ok`, `test_same_requester_and_executor_many_commitments_have_distinct_ids` |

### Additional invariants found during threat analysis
| ID | Invariant | Evidence |
|----|-----------|----------|
| X1 | Hostile input is rejected before any LLM call and in bounded time | `test_oversized_inputs_rejected_before_any_llm_and_quickly`, `test_depth_guard_runs_before_json_parsing` |
| X2 | Hash domains are separated and the encoding is injective | `TestHashingAndDomains` |
| X3 | `MET` never rests only on an unverified external reference | `test_met_cannot_rest_only_on_external_reference` |
