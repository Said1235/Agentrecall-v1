# AgentRecall V1 - Threat model

## Assets
Integrity of commitments and criteria; binding between a delivery and its adjudication;
integrity and honesty of the adjudication record; availability of the adjudication path.

## Actors and trust
| Actor | Trust |
|-------|-------|
| Requester / Executor | Mutually adversarial; each may be malicious. Controls every string they submit. |
| Relayer (anyone) | Untrusted; gains no authority. |
| Leader | May be faulty or malicious (can run modified code). Its output is data. |
| Validators | Assumed to run the unmodified contract; assumed to run LLMs that may be wrong or share biases. |
| LLM providers | Not trusted for correctness or for instruction-following under adversarial input. |
| Submitted URLs / artifacts | Never fetched or executed; treated as unverified text. |

## Trust boundaries
1. Caller input -> contract: validated deterministically (size, charset, JSON depth, ids, kinds, hashes) before any LLM.
2. Contract -> LLM: fixed instructions + escaped JSON data.
3. LLM -> contract: strict shape validation; only enums and ids survive.
4. Leader -> validator: proposal re-validated from scratch and re-derived by independent evaluation.

## Threats and mitigations (summary; the full matrix with tests is in `SECURITY_AUDIT.md`)

| Threat | Mitigation | Residual |
|--------|------------|----------|
| Impersonation / wrong-party actions | per-method caller checks | none known |
| Criteria or evidence changed after commitment | hashes + immutability + hash check before LLM | none known |
| Prompt injection in criteria, delivery, evidence, challenge | contract-owned instructions; data JSON-escaped on one line; fixed output schema; independent validators; outputs reduced to enums/ids | A persuasive injection can still sway an LLM judgement; if it sways all validators' models it succeeds. Not preventable by code. |
| Leader fabricates or omits | exact structural checks + independent per-criterion evaluation + verifier | LLM nondeterminism: honest disagreement causes rotation |
| Technical failure presented as verdict | fail-closed validator; persistence only after consensus | none known |
| Resource exhaustion | byte limits, depth guard, bounded loops, no regex | Provider context limits for the largest allowed package are unknown |
| Griefing by repeated failing relays | each failed relay changes no state | fees borne by relayers |
| Liveness (no majority / UNDETERMINED) | `INDETERMINATE` outcome, strict rubric, retry | cannot be eliminated |
| Privacy | none (design) | All delivery content, evidence and challenge text are in public calldata at submission and again at adjudication |
| Sybil (one person, two addresses) | none | out of scope |
| Appeal reversal of an `ACCEPTED` result | frontends must show finality status | see `FRONTEND_INTEGRATION.md` |

## Out of scope
Authenticity of evidence; authorship; real-world facts; validator collusion; economics of
validators; cross-contract interaction (none exists).
