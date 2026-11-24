# AgentRecall V1 - Frontend integration contract

Audience: a frontend engineer who will **not** read the Python source. Everything below
describes the contract as implemented in `contracts/agent_recall.py`. Items marked
**(unverified)** could not be confirmed against a running GenLayer toolchain; confirm them on
your first integration run.

> Always call `get_limits()` at startup and validate user input against it before sending a
> transaction. Failed transactions cost fees and change nothing.

---

## A. Contract overview

**Purpose.** Records bilateral commitments between exactly two participants and, if the
requester disputes a delivery, produces an immutable adjudication record by GenLayer validator
consensus.

**Roles.** *Requester* creates the commitment and its criteria. *Executor* (a different
address) accepts/rejects and delivers. *Relayer* is anyone who sends the `adjudicate`
transaction; a relayer gains no authority.

**Lifecycle.** `OPEN -> ACCEPTED -> SUBMITTED -> CHALLENGED -> ADJUDICATED`, with terminal
states `REJECTED`, `CANCELLED`, `UNCONTESTED` (section D).

**It does:** store commitments, criteria and hashes of delivered material; adjudicate disputed
deliveries criterion by criterion; keep every record immutable and retrievable by id.

**It does not:** move funds/tokens, apply penalties, track reputation, fetch URLs, run
submitted code, verify authorship or authenticity, apply deadlines, support groups, store the
delivered documents themselves, or store any LLM explanation text.

**Limitations to show users**
- `UNCONTESTED` and silence are **not** positive verdicts.
- Validator agreement is not proof of truth. Show the `limitations` returned with every adjudication.
- `ACCEPTED`, `SUBMITTED`, `CHALLENGED` can last forever (no expiry).
- All delivered material and challenge text is **public** (transaction calldata).
- One submission and one challenge per commitment; no resubmission.

---

## B. Exact public interface

Conventions: **addresses are passed as plain `str` hex addresses** (`0x` + 40 hex characters; the
contract converts them), exactly like the Studio's own examples. `str` ids are 64 lowercase hex
characters. **All structured arguments are JSON-encoded strings** (call
`JSON.stringify` once). Strings must not contain control characters other than `\n \r \t`.
Sizes are UTF-8 bytes. Errors are strings (section H).

### B.1 Write methods

All writes are ordinary GenLayer transactions. Only `adjudicate` runs non-deterministic
(LLM) execution; the others are deterministic. Return values exist but **do not depend on them**:
derive ids with `compute_commitment_id` and read state with the views.

#### `create_commitment`
| | |
|--|--|
| Args | `nonce: str` (1-64 chars of `A-Za-z0-9_-.`), `executor: str` (hex address), `description: str`, `criteria_json: str`, `accepted_evidence_kinds_json: str` |
| Caller | anyone; becomes the **requester** |
| Preconditions | `executor` is a valid address, not the zero address and not the caller; `commitment_id` unused; `criteria_json` is an array of 1..10 objects `{"id","text"}` with unique ids (`id`: 1-32 chars of `A-Za-z0-9_-.`; `text` <= 400 bytes); `accepted_evidence_kinds_json` is a non-empty array of unique values from `TEXT, STRUCTURED, CONTENT_HASH, ARTIFACT, EXTERNAL_REFERENCE`; `description` <= 1500 bytes, non-blank |
| Transition | -> `OPEN` |
| Errors | `INVALID_INPUT`, `INVALID_JSON`, `INPUT_TOO_LARGE`, `DUPLICATE_ID`, `ALREADY_EXISTS` |
| Returns | `str` = commitment id |
| Non-deterministic | no |

Write each criterion as a single, independently checkable condition. Compound criteria hide
partial fulfillment.

#### `accept_commitment(commitment_id: str)`
Caller: the executor. Precondition: `OPEN`. Transition: `OPEN -> ACCEPTED`. Errors: `NOT_FOUND`, `UNAUTHORIZED`, `INVALID_STATE`. Deterministic. Returns nothing.

#### `reject_commitment(commitment_id: str)`
Caller: the executor. Precondition: `OPEN`. Transition: `OPEN -> REJECTED` (terminal). Errors: `NOT_FOUND`, `UNAUTHORIZED`, `INVALID_STATE`. Deterministic.

#### `cancel_commitment(commitment_id: str)`
Caller: the requester. Precondition: `OPEN` (not possible after acceptance). Transition: `OPEN -> CANCELLED` (terminal). Errors: `NOT_FOUND`, `UNAUTHORIZED`, `INVALID_STATE`. Deterministic.

#### `submit_delivery`
| | |
|--|--|
| Args | `commitment_id: str`, `content: str`, `evidence_json: str` |
| Caller | the executor |
| Preconditions | status `ACCEPTED`; `content` 1..6000 bytes, non-blank; `evidence_json` is an array of 0..12 objects `{"id","kind","content"}` (`id` as above and unique; `kind` must be one of the commitment's accepted kinds; `content` non-blank, <= 3000 bytes; total <= 16000 bytes; no two items with the same `kind` and `content`) |
| Transition | `ACCEPTED -> SUBMITTED` |
| Errors | `NOT_FOUND`, `UNAUTHORIZED`, `INVALID_STATE`, `INVALID_INPUT`, `INVALID_JSON`, `INPUT_TOO_LARGE`, `DUPLICATE_ID`, `DUPLICATE_EVIDENCE` |
| Returns | `str` = submission id |
| Non-deterministic | no |

Only hashes and sizes are stored. **Keep the exact `content` and evidence array**; you need
them again for adjudication (section G).

#### `create_challenge`
| | |
|--|--|
| Args | `commitment_id: str`, `statement: str`, `disputed_criterion_ids_json: str`, `challenge_evidence_json: str` |
| Caller | the requester |
| Preconditions | status `SUBMITTED`; `statement` 1..1500 bytes; `disputed_criterion_ids_json` is a non-empty array of unique ids that all belong to the commitment; `challenge_evidence_json` is an array of 0..6 evidence objects (same shape as above, any kind, total <= 8000 bytes) |
| Transition | `SUBMITTED -> CHALLENGED` |
| Errors | `NOT_FOUND`, `UNAUTHORIZED`, `INVALID_STATE`, `INVALID_INPUT`, `INVALID_JSON`, `INPUT_TOO_LARGE`, `DUPLICATE_ID`, `DUPLICATE_EVIDENCE`, `UNKNOWN_CRITERION` |
| Returns | `str` = challenge id |
| Non-deterministic | no |

The disputed list is context only: **adjudication evaluates every criterion** of the commitment.
Tell requesters that challenging one criterion can lead to a `NOT_MET` on another.

#### `close_uncontested(commitment_id: str)`
Caller: the requester. Precondition: `SUBMITTED`. Transition: `SUBMITTED -> UNCONTESTED` (terminal). Errors: `NOT_FOUND`, `UNAUTHORIZED`, `INVALID_STATE`. Deterministic. Meaning: "the requester chose not to challenge". Not a verdict.

#### `adjudicate`
| | |
|--|--|
| Args | `commitment_id: str`, `content: str`, `evidence_json: str`, `challenge_statement: str`, `disputed_criterion_ids_json: str`, `challenge_evidence_json: str` |
| Caller | **anyone** |
| Preconditions | status `CHALLENGED`; every supplied value is **identical** to what was submitted (evidence/id arrays may be in any order) |
| Transition | `CHALLENGED -> ADJUDICATED` only if validator consensus accepts a result |
| Errors | `NOT_FOUND`, `INVALID_STATE`, all input errors above, `HASH_MISMATCH`, `[LLM_ERROR]`, plus consensus-level failures (section F) |
| Returns | `str` = adjudication id |
| Non-deterministic | **yes** (LLM calls by leader and validators) |

Hashes are verified before any LLM call. A failed or undetermined `adjudicate` changes nothing
and may be retried.

### B.2 View methods

| Method | Args | Returns |
|--------|------|---------|
| `compute_commitment_id` | `requester: str` (hex address), `nonce: str` | `str` - the id `create_commitment` will produce/produced |
| `get_limits` | - | object: all numeric limits, `evidence_kinds`, `outcomes`, `overall_outcomes`, `reason_codes` (map outcome -> codes) |
| `get_commitment` | `commitment_id: str` | Commitment object (section C) incl. `status` and child ids |
| `get_submission` | `submission_id: str` | Submission object |
| `get_challenge` | `challenge_id: str` | Challenge object |
| `get_adjudication` | `adjudication_id: str` | Adjudication object |

`get_*` with an unknown id fail with `[EXPECTED] NOT_FOUND`. Child ids appear in
`get_commitment` (`submission_id`, `challenge_id`, `adjudication_id`; empty string `""` until
the child exists) - use them for navigation.

---

## C. Data structures (as returned by the views)

**Commitment** (`get_commitment`)
```json
{
  "commitment_id": "<64 hex>",
  "status": "OPEN | ACCEPTED | REJECTED | CANCELLED | SUBMITTED | CHALLENGED | UNCONTESTED | ADJUDICATED",
  "requester": "0x...", "executor": "0x...",
  "description": "Deliver a risk report",
  "criteria": [ { "id": "C1", "text": "The report lists exactly three risks" },
                { "id": "C2", "text": "The report is shorter than 500 words" } ],
  "accepted_evidence_kinds": ["ARTIFACT", "CONTENT_HASH", "EXTERNAL_REFERENCE", "STRUCTURED", "TEXT"],
  "commitment_hash": "<64 hex>",
  "created_at": "<string provided by the VM, format unverified>",
  "submission_id": "", "challenge_id": "", "adjudication_id": ""
}
```
(`accepted_evidence_kinds` is returned sorted.)

**Evidence item** (input only; the contract never returns the content)
```json
{ "id": "E1", "kind": "TEXT", "content": "Draft word count is 120" }
```

**Submission** (`get_submission`)
```json
{ "submission_id": "<64 hex>", "commitment_id": "<64 hex>", "executor": "0x...",
  "status": "SUBMITTED | CHALLENGED | CLOSED_UNCONTESTED | ADJUDICATED",
  "content_hash": "<64 hex>", "evidence_manifest_hash": "<64 hex>", "submission_hash": "<64 hex>",
  "content_bytes": 50, "evidence_count": 2, "created_at": "..." }
```

**Challenge** (`get_challenge`)
```json
{ "challenge_id": "<64 hex>", "commitment_id": "<64 hex>", "submission_id": "<64 hex>",
  "requester": "0x...", "status": "OPEN | ADJUDICATED",
  "statement": "Only two risks are listed in the report",
  "disputed_criterion_ids": ["C1"], "challenge_hash": "<64 hex>",
  "evidence_count": 1, "created_at": "..." }
```

**Criterion result** (inside an adjudication)
```json
{ "criterion_id": "C1", "outcome": "MET | NOT_MET | INDETERMINATE",
  "reason_codes": ["EVIDENCE_SUFFICIENT"], "evidence_ids": ["S:#DELIVERY", "S:E1"] }
```
Evidence id namespace: `S:#DELIVERY` = the delivery text; `S:<id>` = executor evidence;
`C:<id>` = requester challenge evidence.

Reason codes by outcome: `MET`: `EVIDENCE_SUFFICIENT`. `NOT_MET`: `EVIDENCE_CONTRADICTS`,
`REQUIREMENT_NOT_ADDRESSED`, `DELIVERY_INCOMPLETE`. `INDETERMINATE`: `EVIDENCE_INSUFFICIENT`,
`EVIDENCE_AMBIGUOUS`, `EVIDENCE_CONFLICTING`, `UNVERIFIABLE_CLAIM`.

**Adjudication** (`get_adjudication`)
```json
{ "adjudication_id": "<64 hex>", "commitment_id": "<64 hex>", "submission_id": "<64 hex>",
  "challenge_id": "<64 hex>", "commitment_hash": "<64 hex>", "submission_hash": "<64 hex>",
  "challenge_hash": "<64 hex>", "evidence_package_hash": "<64 hex>", "schema_version": 1,
  "overall_outcome": "FULFILLED | PARTIALLY_FULFILLED | NOT_FULFILLED | INDETERMINATE",
  "criteria_results": [ { "criterion_id": "C1", "outcome": "NOT_MET",
      "reason_codes": ["DELIVERY_INCOMPLETE"], "evidence_ids": ["S:#DELIVERY"] },
    { "criterion_id": "C2", "outcome": "MET", "reason_codes": ["EVIDENCE_SUFFICIENT"],
      "evidence_ids": ["S:#DELIVERY", "S:E1"] } ],
  "result_hash": "<64 hex>",
  "limitations": ["ONLY_SUBMITTED_MATERIAL_EVALUATED", "EXTERNAL_REFERENCES_NOT_FETCHED_OR_VERIFIED",
                  "NO_CODE_OR_ARTIFACT_EXECUTION", "AUTHORSHIP_AND_AUTHENTICITY_NOT_VERIFIED",
                  "VALIDATOR_AGREEMENT_IS_NOT_PROOF_OF_TRUTH"],
  "relayed_by": "0x...", "created_at": "..." }
```
`overall_outcome` is **derived** from the criteria: any `NOT_MET` -> `PARTIALLY_FULFILLED`
(some `MET`) or `NOT_FULFILLED` (no `MET`); else any `INDETERMINATE` -> `INDETERMINATE`; else
`FULFILLED`. There is no free-text explanation; render the structured fields and map codes to
your own user-facing wording. Never infer additional verdicts.

---

## D. State machine

| Current state | Caller | Operation | Next state | Conditions | Terminal |
|---------------|--------|-----------|------------|------------|----------|
| - | anyone (-> requester) | `create_commitment` | `OPEN` | valid input | no |
| `OPEN` | executor | `accept_commitment` | `ACCEPTED` | - | no |
| `OPEN` | executor | `reject_commitment` | `REJECTED` | - | yes |
| `OPEN` | requester | `cancel_commitment` | `CANCELLED` | - | yes |
| `ACCEPTED` | executor | `submit_delivery` | `SUBMITTED` | valid material | no |
| `SUBMITTED` | requester | `create_challenge` | `CHALLENGED` | valid challenge | no |
| `SUBMITTED` | requester | `close_uncontested` | `UNCONTESTED` | - | yes |
| `CHALLENGED` | anyone | `adjudicate` | `ADJUDICATED` | hashes match; consensus accepted | yes |

**`UNCONTESTED` vs a successful adjudication.** `UNCONTESTED` means only: *the requester
explicitly decided not to challenge.* No validator evaluated anything; there is no adjudication
record. Display it as "Closed without dispute", never as "Fulfilled" or "Verified". A
**successful adjudication** is `ADJUDICATED` with an adjudication record whose `overall_outcome`
may be any of the four values - including `NOT_FULFILLED` and `INDETERMINATE`.
`INDETERMINATE` is a valid business result ("the evidence cannot decide"), **not** an error.

---

## E. Frontend workflow

1. **Create commitment.** Collect description, criteria (atomic!), accepted evidence kinds, executor address, a unique `nonce`. Validate with `get_limits`. Send `create_commitment`. Derive the id with `compute_commitment_id(requester, nonce)`.
2. **Pending acceptance.** Poll `get_commitment(id)`; show `OPEN`. The requester may `cancel_commitment`.
3. **Accept/reject.** The executor sees the criteria exactly as committed and calls `accept_commitment` or `reject_commitment`. Show `REJECTED` as "Declined by executor", not as a breach.
4. **Submit delivery.** Build `content` and the evidence array; **persist both verbatim** (section G); send `submit_delivery`.
5. **Submitted state.** Show `SUBMITTED` with the hashes and sizes (`get_submission`). Say clearly that nothing has been verified.
6. **Challenge.** The requester selects disputed criteria, writes a statement, optionally attaches evidence; send `create_challenge`. Persist statement, ids and evidence verbatim.
7. **Close unchallenged.** Offer `close_uncontested` with a confirmation dialog explaining it ends the dispute opportunity and is not a verdict.
8. **Request adjudication.** From `CHALLENGED`, any user can press "Adjudicate". Your app must supply the original material (section G). Show a cost/latency warning: LLM execution runs on several validators.
9. **Monitor.** Track the transaction (section F); meanwhile `get_commitment` still reports `CHALLENGED`.
10. **Display final adjudication.** When `get_commitment().adjudication_id` is non-empty, call `get_adjudication`. Show per-criterion results, `overall_outcome`, hashes and the `limitations`. Mark it provisional until the transaction is `FINALIZED`.

---

## F. Transaction lifecycle

Statuses below are from the official *Transaction Statuses* documentation. Do not invent others.

| Status | Meaning for your UI |
|--------|---------------------|
| `PENDING` | Submitted, waiting to be processed. Show "submitted". |
| `PROPOSING` | A leader is executing. For `adjudicate` this is where the LLM runs. |
| `COMMITTING` / `REVEALING` | Validators vote. Show "validating". |
| `ACCEPTED` | Consensus reached. **Not final**: an appeal can change it before finality. |
| `FINALIZED` | Final. Only now treat an adjudication as definitive. |
| `UNDETERMINED` | Validators could not agree (after rotations). **Nothing was persisted.** Offer "retry". |
| `CANCELED` | Cancelled before completion. Nothing persisted. |

### Fees and network (Studio v0.123, live on studio.genlayer.com since 23 Nov 2026)

- **Every deploy and write needs fees.** Estimate them first (`estimateTransactionFees` /
  `estimateTransactionFeesForWrite` in genlayer-js 2.0.0, `estimate_transaction_fees` in
  genlayer-py 0.19.0, `genlayer estimate-fees` in CLI 0.40.0) and pass `fees` (`distribution`,
  `feeValue`) with the write. Without them the transaction fails with `FeesDistributionMissing`
  (or `FeeValueMustBeNonZero`). The Studio UI does this automatically; your app must do it itself.
  These are fee errors, not contract errors.
- `adjudicate` runs several LLM calls on several validators, so estimate its fee with the
  write-specific estimator and show it to the user before sending (Transaction Kit:
  https://docs.genlayer.com/developers/decentralized-applications/fees-and-transaction-kit).
- Chain ID **61999** on studio.genlayer.com (61997 on Studio Next). When sending several
  transactions from one account, wait for each submission to return before signing the next
  (you do not need to wait for finalization).
- Use genlayer-js 2.0.0 or newer; older SDKs can read but cannot deploy or write.
- Check **both** the transaction status and its execution result after every transaction (also
  stated in the official announcement).

Rules for your UI:
1. "Transaction submitted" is not "adjudicated". Only `get_commitment().status == "ADJUDICATED"` (plus an `adjudication_id`) means a result exists.
2. A transaction can reach `ACCEPTED`/`FINALIZED` **with an execution error** (for example a contract `UserError`). Always check the execution result as well as the status (the genlayer-js examples inspect `txExecutionResultName`) **(unverified; confirm field names in your genlayer-js version)**, and re-read contract state afterwards.
3. A rolled back / failed / undetermined transaction leaves the commitment in its previous state (`CHALLENGED` stays `CHALLENGED`). Offer retry.
4. Reads can target accepted or finalized state (genlayer-js `readContract` has a state-status option, shown as `stateStatus` in public examples) **(unverified; confirm the exact parameter and values)**. Use finalized state for anything you present as definitive.
5. Failure causes you will meet: contract errors (section H), `[LLM_ERROR]` (leader could not produce a valid evaluation), validator disagreement, `UNDETERMINED`.

---

## G. Evidence resubmission

The contract stores **hashes, not documents**. The contract does not return the original
content, evidence items or challenge evidence. (It does return the challenge `statement`, but
you should still resend your own stored copy.)

For `adjudicate` you must resend, **byte-for-byte**:

| Argument | Must equal | Notes |
|----------|-----------|-------|
| `content` | the `content` used in `submit_delivery` | exact characters, including whitespace and line endings |
| `evidence_json` | the evidence array of `submit_delivery` | order irrelevant; each item's `id`, `kind`, `content` exact |
| `challenge_statement` | the `statement` of `create_challenge` | exact |
| `disputed_criterion_ids_json` | the disputed ids of `create_challenge` | order irrelevant |
| `challenge_evidence_json` | the challenge evidence array | order irrelevant; `[]` if none |

The contract recomputes the content hash, evidence-manifest hash and challenge hash and
compares them with the stored ones **before any LLM call**; any difference fails with
`[EXPECTED] HASH_MISMATCH` and changes nothing. The contract never silently evaluates
different content.

What to preserve: save the exact payloads at submission/challenge time (local storage, your
backend, or an archive). The original transaction calldata on-chain also contains them; how to
fetch and decode it with genlayer-js is **not** defined by this contract and was **not
verified**. Do not rebuild material from memory of what the user typed.

---

## H. Error handling

Contract errors are strings: `[EXPECTED] CODE` or `[EXPECTED] CODE: detail`, and
`[LLM_ERROR] ...`. Match on the prefix and `CODE`; do not parse the detail. How the string is
surfaced (receipt vs. exception) depends on the client **(unverified)**.

| Error | Class | Cause | Recommended UI response |
|-------|-------|-------|-------------------------|
| `UNAUTHORIZED` | business | Wrong caller for this operation | Hide/disable the action for this account |
| `INVALID_STATE` | business | Operation not allowed in the current status (also double-submits) | Refresh `get_commitment`; show current status |
| `NOT_FOUND` | business | Unknown commitment/submission/challenge/adjudication id | Check the id; offer navigation from the parent |
| `ALREADY_EXISTS` | business | `nonce` already used by this requester (or adjudication already exists) | Generate a new nonce |
| `INVALID_INPUT` | input | Field missing, wrong type/shape, illegal characters, blank text, unaccepted evidence kind, zero/self executor | Show field-level message; re-validate with `get_limits` |
| `INVALID_JSON` | input | A `*_json` argument is not valid JSON | Bug in your serialization |
| `INPUT_TOO_LARGE` | input | Exceeds a size/count limit | Show the limit from `get_limits` |
| `DUPLICATE_ID` | input | Repeated criterion id, evidence id, disputed id or kind | Fix duplicates |
| `DUPLICATE_EVIDENCE` | input | Same kind and content under two ids | Remove the duplicate |
| `UNKNOWN_CRITERION` | input | Disputed id is not a criterion of the commitment | Re-select criteria |
| `HASH_MISMATCH` | business | Re-supplied material differs from the original | Reload the stored original payloads; do not retry blindly |
| `[LLM_ERROR]` | technical | Leader's evaluation failed or was malformed | Nothing persisted; offer retry later |
| `FeesDistributionMissing`, `FeeValueMustBeNonZero` | fee | Fees were not attached to the deploy/write | Estimate fees and resend (see section F) |
| Consensus failure / `UNDETERMINED` / `CANCELED` | technical | Validators disagreed or transaction cancelled | Nothing persisted; offer retry |

Never convert a technical failure into a verdict in your UI.

---

## I. Integration examples

Illustrative ids are shown as `<id>`; real ids are 64 hex characters. Address values are examples.

**1. Successful commitment**
```json
{ "method": "create_commitment",
  "args": ["risk-report-2026-001", "0x2222222222222222222222222222222222222222",
           "Deliver a risk report",
           "[{\"id\":\"C1\",\"text\":\"The report lists exactly three risks\"},{\"id\":\"C2\",\"text\":\"The report is shorter than 500 words\"}]",
           "[\"TEXT\",\"EXTERNAL_REFERENCE\"]"] }
```
Then `compute_commitment_id(requester, "risk-report-2026-001")` -> `<id>`; `get_commitment(<id>).status == "OPEN"`; after the executor's `accept_commitment` -> `"ACCEPTED"`.

**2. Rejected commitment:** executor calls `reject_commitment(<id>)` -> `status: "REJECTED"`. Display: "Declined by executor".

**3. Submission**
```json
{ "method": "submit_delivery",
  "args": ["<id>", "Risks: 1) delay 2) cost 3) scope. Word count: 120.",
           "[{\"id\":\"E1\",\"kind\":\"TEXT\",\"content\":\"Draft word count is 120\"},{\"id\":\"E2\",\"kind\":\"EXTERNAL_REFERENCE\",\"content\":\"https://example.com/report\"}]"] }
```
-> `status: "SUBMITTED"`. (E2 is stored as a reference only; the contract never opens the URL, and a `MET` result can never rest on it alone.)

**4. Challenge**
```json
{ "method": "create_challenge",
  "args": ["<id>", "Only two risks are listed in the report", "[\"C1\"]",
           "[{\"id\":\"X1\",\"kind\":\"TEXT\",\"content\":\"Report lists delay and cost only\"}]"] }
```
-> `status: "CHALLENGED"`.

**5. Unchallenged closure:** requester calls `close_uncontested(<id>)` -> `status: "UNCONTESTED"`, `adjudication_id: ""`. UI text: "Closed without dispute - not verified".

**6. Successful adjudication**
```json
{ "method": "adjudicate",
  "args": ["<id>", "Risks: 1) delay 2) cost 3) scope. Word count: 120.",
           "[{\"id\":\"E1\",...},{\"id\":\"E2\",...}]",
           "Only two risks are listed in the report", "[\"C1\"]",
           "[{\"id\":\"X1\",...}]"] }
```
(each `...` = the identical original item). Once the transaction is accepted/finalized, `get_commitment(<id>).status == "ADJUDICATED"`; read `get_adjudication(adjudication_id)`; an example result is in section C.

**7. Indeterminate business verdict.** `get_adjudication(...)` returns e.g. `overall_outcome: "INDETERMINATE"` with `criteria_results` such as
`{"criterion_id":"C1","outcome":"INDETERMINATE","reason_codes":["EVIDENCE_AMBIGUOUS"],"evidence_ids":[]}`.
The transaction **succeeded**; the commitment is `ADJUDICATED`. Show "Evidence insufficient to decide".

**8. Failed technical transaction.** `adjudicate` ends `UNDETERMINED`, or its execution result carries `[LLM_ERROR] leader evaluation failed`. `get_commitment(<id>).status` is still `"CHALLENGED"` and `adjudication_id` is `""`. Show "Could not be adjudicated this time - try again"; do not display any verdict.

Invalid examples (all rejected): `create_commitment` with `criteria_json = "[]"`; with two criteria both `"id":"C1"`; `submit_delivery` with `evidence_json = "{\"id\":\"E1\"}"` (object, not array); an evidence item with an extra field; `adjudicate` with `content` differing by one trailing space (`HASH_MISMATCH`).

---

## J. Integration checklist

- [ ] Call `get_limits()` once; enforce limits client-side (bytes, not characters).
- [ ] Serialize every `*_json` argument with a single `JSON.stringify`; never send objects.
- [ ] Generate a unique `nonce` per commitment; derive ids with `compute_commitment_id`.
- [ ] Do not rely on write return values; read state with the views.
- [ ] Persist the exact `content`, evidence arrays, challenge statement, disputed ids and challenge evidence.
- [ ] Gate buttons by `status` and by the connected account (requester / executor / anyone).
- [ ] Show `UNCONTESTED` as "closed without dispute", never as fulfilled.
- [ ] Treat `INDETERMINATE` as a result, and failures/`UNDETERMINED` as non-results with a retry option.
- [ ] Show the `limitations` list with every adjudication; show no verdict from missing data.
- [ ] Distinguish submitted / executing / accepted / finalized / failed; mark adjudications provisional until `FINALIZED`.
- [ ] Estimate and attach fees to every write (estimator per SDK); use chain ID 61999 and genlayer-js >= 2.0.0.
- [ ] Check the execution result of a transaction, not only its status, and re-read state afterwards.
- [ ] Confirm the **(unverified)** items against your installed genlayer-js version.
