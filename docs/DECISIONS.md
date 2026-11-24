# AgentRecall V1 - Decisions

Status of each decision: **BINDING** = given by the project owner in the decision brief;
**ENGINEERING** = chosen during implementation and recorded here. Nothing below is presented
as user-confirmed unless it says BINDING.

## A. Binding decisions (from the owner's decision brief)

| ID | Decision | Effect in code |
|----|----------|----------------|
| B1 | Consensus must not require identical LLM prose; verification is criterion-by-criterion with a closed vocabulary `MET / NOT_MET / INDETERMINATE`, fixed reason codes, evidence ids; no free-form findings array. | `_canonical_results`, `_check_proposal`, validator rule in `adjudicate` |
| B2 | `UNCONTESTED` is reached only by an explicit requester action; no deadlines, no time-based transitions. | `close_uncontested` |
| B3 | Only the requester can challenge. Adjudication is permissionless once a challenge exists; the caller re-supplies the original material, verified by hash before any LLM call. | `create_challenge`, `adjudicate` |
| B4 | Only the requester can cancel, only while `OPEN`. Executor may reject an `OPEN` commitment. No cancellation after acceptance, no expiry. An accepted commitment may stay `ACCEPTED` forever. | `cancel_commitment`, `reject_commitment` |
| B5 | Local Studio deployment is allowed (and required for integration tests). No public network or testnet deployment. | Nothing was deployed. |
| B6 | `gl.vm.run_nondet_default` is the initial candidate API, subject to verification. | Used in `adjudicate`. |
| B7 | All code, README and docs are written in English. | - |

## B. Engineering decisions

| ID | Decision | Alternatives considered | Why |
|----|----------|-------------------------|-----|
| E1 | Structured arguments (`criteria_json`, `evidence_json`, ...) are passed as **JSON-encoded strings**. | Typed `list[dict[str,str]]` arguments. | Schema reflection of nested generic argument types could not be tested here (no linter/SDK). A plain `str` cannot break schema loading, and it is the argument type of the Studio's own example. Cost: callers `JSON.stringify` once. Revisit after `genvm-lint schema` is run. |
| E2 | IDs are **derived**, not allocated: `commitment_id = H(requester, nonce)`, `submission_id = H(commitment_id)`, `challenge_id = H(submission_id)`, `adjudication_id = H(challenge_id)`. Caller supplies `nonce`. | Auto-increment counter; hash of tx. | No shared counter (no overwrite/race), exact lookup, parent lookup without scanning, ids bound to the requester address. `compute_commitment_id` lets clients derive the id without reading tx results. |
| E3 | Lifecycle status lives in **one** map (`commitment_status`); submission/challenge "status" in views is derived from it. Records are never mutated after creation. | Status fields on every record. | Removes the possibility of contradictory stored statuses and of partial mutation. |
| E4 | The **contract computes all hashes**; callers send raw material, never hashes. | Caller-supplied hashes. | Removes frontend hashing risk and the "caller commits to something else" class of bugs. Cost: material is in calldata at submission and again at adjudication (bounded by limits). |
| E5 | Hash encoding is a custom **type-tagged, length-prefixed, domain-separated** byte format hashed with `genlayer.types.Keccak256`. | `calldata.encode` / JSON. | The reference does not state that calldata or JSON encoding is canonical for dicts; a bespoke injective encoding is verifiable by inspection and by test. |
| E6 | Citable evidence ids are namespaced: `S:#DELIVERY` (the delivery text), `S:<id>` (executor evidence), `C:<id>` (requester challenge evidence). `#` is not a legal id character so the delivery id cannot collide. | Global id space with collision checks. | Collisions are impossible by construction; no cross-record lookup needed at challenge time. |
| E7 | Evidence kinds: `TEXT, STRUCTURED, CONTENT_HASH, ARTIFACT, EXTERNAL_REFERENCE`. The commitment lists the kinds the executor may submit; challenge evidence may use any kind. | Free-form kinds. | Closed vocabulary; supports the spec's evidence model. |
| E8 | Reason codes are a closed vocabulary **partitioned by outcome** (`MET`: 1 code; `NOT_MET`: 3; `INDETERMINATE`: 4); 1-2 codes per criterion. | Free-text reasons. | Deterministically checkable; no prose in the proposal. |
| E9 | Validators compare **per-criterion `outcome` exactly**. `reason_codes` and `evidence_ids` are **not** compared for equality; they are checked structurally and then judged by an independent **verifier** call (SUPPORTED / UNSUPPORTED per criterion). | Exact equality of reason codes and evidence ids. | Two honest LLM runs legitimately cite different evidence or pick different reasons for the same outcome; exact equality would cause avoidable consensus failures. This follows B1. Residual risk is documented in `CONSENSUS_DESIGN.md`. |
| E10 | Overall outcome is **derived**, never proposed freely: any `NOT_MET` -> `PARTIALLY_FULFILLED` if some `MET` else `NOT_FULFILLED`; else any `INDETERMINATE` -> `INDETERMINATE`; else `FULFILLED`. | LLM-proposed overall verdict. | Prevents an overall verdict that contradicts criterion results. |
| E11 | **No narrative text is stored** in the adjudication. Limitations are contract-defined constants returned with every adjudication. | Store an LLM explanation. | A narrative would be unverified model text; excluding it removes a prompt-injection sink and a source of unbound claims. |
| E12 | **Every committed criterion is evaluated**, not only the criteria listed in the challenge. The disputed list is context for the evaluator. **This is a product-impacting choice**: a challenge on `C1` can result in `NOT_MET` for an undisputed `C2`. | Evaluate only disputed criteria and treat the rest as accepted. | B1 says every committed criterion must appear exactly once. The alternative needs an explicit owner decision. |
| E13 | Leader technical errors (LLM error, malformed output) are **never accepted**: validators return `False`, which forces disagreement/rotation instead of locking in a failure. State is untouched. | Agree on identical error messages. | Follows the "classify errors" pattern in the official error-handling page: LLM errors should rotate the leader. |
| E14 | A manifest may not contain two items with identical `(kind, content)` under different ids. | Allow duplicates. | Deterministic defence against duplicate corroboration. |
| E15 | A `MET` result must cite at least one item that is not `EXTERNAL_REFERENCE`. | Allow reference-only support. | External URLs are never fetched or verified in V1. |
| E16 | `requester != executor` and `executor != zero address`. | Allow self-commitments. | Not a bilateral commitment otherwise. (Two addresses controlled by one person cannot be detected.) |
| E17 | Size limits are in UTF-8 **bytes**, chosen conservatively (see `get_limits`). They are application limits, not protocol limits. | Protocol maxima. | The reference does not publish an input maximum; limits keep the two-to-three LLM prompts bounded. |
| E18 | `created_at` is `gl.message.raw["datetime"]` (string, as provided by the VM). Its exact format is **not verified**. | Integer timestamps. | `raw["datetime"]` is documented as the transaction datetime; no other time source used. |
| E19 | No events are emitted. | Emit `gl.chain.Event`s. | Not required; avoids unverified API surface. Frontends read state. |
| E20 | `exec_prompt` is called in **plain text mode** (as in the Studio's own example). The answer is parsed by the contract: surrounding markdown fences tolerated, <= 20 000 bytes, nesting depth <= 6, then strict shape validation. An already-parsed value passes through. | `response_format="json"`. | Mirrors the Studio example; avoids version-dependent JSON-mode behaviour in test tooling (playbook section 5.3). Revised after the first delivery failed to deploy. |
| E21 | **Addresses are `str` arguments** (`executor`, `requester`), converted with `Address(...)`; invalid or zero addresses -> `INVALID_INPUT`. | `Address`-typed arguments. | The Studio's working example uses `str` for addresses; fewer schema-generation unknowns. An AST test enforces `str` for every public argument. |
| E22 | **Header = exactly two leading comment lines** (`# v0.4.0`, then the `Depends` JSON), then a blank line. Design comments come after the imports. | Descriptive header comments. | GenVM parses the whole leading comment block as the runner JSON (genlayer-docs #487); anything else makes the deploy fail with `invalid_contract runner malformed`. Regression-tested. |
| E23 | **Keccak-256**: SDK `Keccak256` from `genlayer.types`, else `genlayer.types.keccak`, else a pure-Python implementation (verified against published vectors and, for the permutation, against `hashlib.sha3_256`). SDK errors at runtime also fall back. | SDK only. | The import path was never verified in the author's environment; a failed import would make the contract undeployable. Cost of the fallback: ~0.3 s per 40 KB in CPython; slower inside GenVM. |
| E24 | No v0.2 build. | Maintain a `1jb45aa8...` variant. | Studio v0.123 (23 Nov 2026) requires v0.4 for new contracts; v0.2 support is being removed. |

## C. Explicitly out of scope for V1 (documented, not implemented)

Group commitments, payments/escrow/tokens, reputation, deadlines/expiry, resubmission, multiple
challenges, web fetching of evidence, execution of submitted artifacts, narrative explanations.
