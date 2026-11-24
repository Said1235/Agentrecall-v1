# AgentRecall V1 - State machine

Single source of truth: `commitment_status` (one entry per commitment). There is no other
mutable status. All transitions are executed by the methods below; there is no way to set a
status directly.

## Transition table

| Current state | Allowed caller | Operation | Next state | Conditions | Terminal? |
|---------------|----------------|-----------|------------|------------|-----------|
| *(none)* | anyone (becomes requester) | `create_commitment` | `OPEN` | valid input; executor != requester, != zero address; id not yet used | no |
| `OPEN` | executor | `accept_commitment` | `ACCEPTED` | - | no |
| `OPEN` | executor | `reject_commitment` | `REJECTED` | - | **yes** |
| `OPEN` | requester | `cancel_commitment` | `CANCELLED` | - | **yes** |
| `ACCEPTED` | executor | `submit_delivery` | `SUBMITTED` | valid content and evidence (kinds accepted by the commitment) | no |
| `SUBMITTED` | requester | `create_challenge` | `CHALLENGED` | valid statement, >=1 known disputed criterion id | no |
| `SUBMITTED` | requester | `close_uncontested` | `UNCONTESTED` | - | **yes** |
| `CHALLENGED` | **anyone** | `adjudicate` | `ADJUDICATED` | re-supplied material matches stored hashes; consensus returned an accepted proposal | **yes** |

Every other `(state, operation)` pair fails with `[EXPECTED] INVALID_STATE` (or
`[EXPECTED] UNAUTHORIZED` when the caller is wrong; authorization is checked first). This is
tested exhaustively: `test_state_transition_matrix` runs all 8 states x 7 operations and checks
that a rejected transition leaves the state unchanged.

## State semantics

| State | Meaning | It does **not** mean |
|-------|---------|----------------------|
| `OPEN` | Commitment created, waiting for the executor. | Executor has agreed. |
| `ACCEPTED` | Executor accepted the criteria as written. May remain here forever (no expiry in V1). | Work was delivered. |
| `REJECTED` | Executor declined while `OPEN`. | That the executor breached anything. |
| `CANCELLED` | Requester withdrew while `OPEN`. Impossible after acceptance or adjudication. | - |
| `SUBMITTED` | Delivery committed (hashes stored). Stays here until the requester acts. | The delivery is correct or verified. |
| `CHALLENGED` | Requester opened the dispute; adjudication may be relayed by anyone. May stay here if adjudication keeps failing technically. | Any verdict. |
| `UNCONTESTED` | The requester **explicitly** chose not to challenge. | Fulfilled, verified, or a positive GenLayer verdict. No adjudication record exists. |
| `ADJUDICATED` | An accepted adjudication record exists (`adjudication_id` in `get_commitment`). The business result is `overall_outcome` inside it (`INDETERMINATE` is a legitimate business result). | That the claims are objectively true (see `CONSENSUS_DESIGN.md`). |

## Derived statuses in views

- `get_submission().status`: `SUBMITTED` | `CHALLENGED` | `CLOSED_UNCONTESTED` | `ADJUDICATED`.
- `get_challenge().status`: `OPEN` | `ADJUDICATED`.

## Technical failures are not states

A transaction that fails, is rolled back, is `UNDETERMINED`, or whose validators disagree
leaves the commitment in its previous state. A failed `adjudicate` can be retried with a new
transaction while the commitment is still `CHALLENGED`.

## Known limitations of the lifecycle

- `ACCEPTED`, `SUBMITTED` and `CHALLENGED` can persist indefinitely.
- One submission and one challenge per commitment; no resubmission workflow.
