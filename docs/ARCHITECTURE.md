# AgentRecall V1 - Architecture

Single file: `contracts/agent_recall.py`. Runner: `py-genlayer:kzybg95x...` (single-file GenVM v0.4 runner,
announced for new contracts on studio.genlayer.com on 23 Nov 2026). The header is exactly two comment lines
(`# v0.4.0` and the runner JSON) followed by a blank line. No constructor arguments, no secrets, no external
services, no web access.

## 1. Storage

| Map (`TreeMap`) | Key | Value | Written by | Mutated later? |
|-----------------|-----|-------|------------|----------------|
| `commitments` | `commitment_id` | `Commitment` | `create_commitment` | never |
| `commitment_status` | `commitment_id` | `str` (state) | every transition | yes (only this map) |
| `submissions` | `submission_id` | `Submission` | `submit_delivery` | never |
| `challenges` | `challenge_id` | `Challenge` | `create_challenge` | never |
| `adjudications` | `adjudication_id` | `Adjudication` | `adjudicate` | never |

Records are `@gl.storage.allow @dataclasses.dataclass` classes whose fields are only `str`,
`Address` and `u32`. Structured values (criteria, kinds, disputed ids, criterion results) are
stored as compact JSON strings (re-parsed by the views). Large material is **not** stored, only
its hashes plus bounded metadata (`content_bytes`, `evidence_count`). The challenge `statement`
(<= 1500 bytes) is stored in clear.

## 2. Identifiers

```
commitment_id   = H("COMMITMENT_ID",   requester_bytes, nonce)      nonce chosen by the requester
submission_id   = H("SUBMISSION_ID",   commitment_id)
challenge_id    = H("CHALLENGE_ID",    submission_id)
adjudication_id = H("ADJUDICATION_ID", challenge_id)
```
Ids are 64-hex-character strings. They are derived, so a parent id determines its children's ids
and `get_commitment` reports each child id as soon as the child exists.

## 3. Hashes and domain separation

`H(domain, *parts) = Keccak256( enc("AGENTRECALL/V1/" + domain) || enc([parts]) )`, where `enc` is
injective: strings `S|len4|bytes`, bytes `B|len4|bytes`, non-negative ints `I|len4|ascii`, lists
`L|count4|items`. Booleans, negatives, floats, dicts, `None` raise `TypeError`.

| Hash | Domain | Parts |
|------|--------|-------|
| commitment_hash | `COMMITMENT` | commitment_id, requester, executor, description, [[crit id, text]...], sorted kinds |
| content_hash | `SUBMISSION_CONTENT` | commitment_id, content |
| evidence_manifest_hash | `EVIDENCE_MANIFEST` | commitment_id, [[id, kind, content]...] sorted by id |
| submission_hash | `SUBMISSION` | commitment_id, executor, content_hash, manifest_hash |
| challenge_hash | `CHALLENGE_MATERIAL` | submission_id, requester, statement, sorted disputed ids, [[id, kind, content]...] sorted by id |
| evidence_package_hash | `EVIDENCE_PACKAGE` | commitment_hash, submission_hash, challenge_hash |
| result_hash | `ADJUDICATION_RESULT` | schema version, ids, package hash, overall, per-criterion tuples |

Evidence items are sorted by id before hashing and before prompting, so caller ordering is
irrelevant. Domain separation and injectivity are tested (`TestHashingAndDomains`).
The SDK's `Keccak256` is used when importable (`genlayer.types`, else `genlayer.types.keccak`); otherwise,
or if it raises, a pure-Python Keccak-256 (checked against published vectors) is used. Both are
standard Keccak-256, so hashes do not depend on which path ran.

## 4. Evidence package (what the LLM sees)

`S:#DELIVERY` (delivery text), `S:<id>` (executor items), `C:<id>` (requester challenge items).
Plus: commitment description, criteria (`{id, text}`), accepted evidence kinds, and the
challenge statement (labelled `requester_allegation`, not citable).

## 5. Prompt construction

Fixed instructions + a single-line JSON `DATA` document produced by
`json.dumps(..., ensure_ascii=True, separators=(",", ":"))`. All participant text therefore
sits inside JSON strings with quotes, newlines and every non-ASCII character escaped. Roles are
`ROLE: EVALUATOR` and `ROLE: VERIFIER`. Delimiters are not relied on as a defence by themselves;
see `THREAT_MODEL.md`.

## 6. Input bounds

All limits are UTF-8 bytes and are returned by `get_limits()`:
description 1500, criteria <= 10 x 400, content 6000, evidence <= 12 items x 3000 (16000 total),
challenge statement 1500, challenge evidence <= 6 items (8000 total), ids <= 32 chars, nonce
<= 64. JSON arguments must have nesting depth <= 2, checked by a linear scan **before**
`json.loads`. Every loop is bounded by these limits; there are no regular expressions and no
HTML processing. Oversized or hostile input is rejected deterministically before any LLM call.

## 7. Methods

Writes: `create_commitment`, `accept_commitment`, `reject_commitment`, `cancel_commitment`,
`submit_delivery`, `create_challenge`, `close_uncontested`, `adjudicate`.
Views: `compute_commitment_id`, `get_limits`, `get_commitment`, `get_submission`,
`get_challenge`, `get_adjudication`. Exact signatures: `FRONTEND_INTEGRATION.md`.

## 8. Not implemented (by design)

Groups, payments, tokens, reputation, deadlines, resubmission, URL fetching, code execution,
narrative explanations, events, upgrade hooks.
