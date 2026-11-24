# AgentRecall V1 - Research record

Date of research: 2026-11-23. Environment: a chat sandbox with **no repository, no network for
shell commands, no Docker, no pytest, no genlayer / genvm-lint / gltest packages** (see section
3). Documentation was read through a web-fetch tool; nothing was installed or inspected on a
real GenLayer toolchain.

## 1. Sources actually read

| Source | Section | What it establishes | Decision that depends on it | Available in installed env? | Discrepancy / uncertainty |
|--------|---------|---------------------|-----------------------------|-----------------------------|----------------------------|
| SDK reference `sdk.genlayer.com/main/_static/ai/api.txt` | Available Runners / Changelog | Current SDK is **v0.4.0-rc1**; `py-genlayer` hash `kzybg95x1gn21dw72m7hyg0maaap04n4nx55j9yt6fkdqxtz6bz0`; `py-genlayer-multi` for multi-file | Single-file runner and its hash in line 2 of the contract (line 1 is the `# v0.4.0` marker) | Not installable here | Examples and the skills file use the older hash `1jb45aa8...` (GenVM v0.2). The 16/23 Nov 2026 announcements confirm `kzybg95x...` for new contracts. |
| same | Migration guide v0.2 -> v0.3/0.4 | `import genlayer as gl` + `from genlayer.types import *`; `gl.Contract` -> `gl.contract.Contract`; `gl.storage.allow/TreeMap/DynArray`; `UserError(data)` with `.data`; type aliases not callable; `run_nondet` renamed meanings; `Keccak` module path | All imports and decorators | - | Supplied examples (v0.2.16/17) use the **old** syntax and were not copied |
| same | `genlayer.vm` | `run_nondet_default(leader_fn, validator_fn, ...)`, `Result = Return \| VMError \| UserError`, `Return.calldata`, validator runs in sandbox; generic `run_nondet` is unsafe | Consensus API choice (B6 confirmed as reasonable) | - | Behaviour at runtime unverified |
| same | `genlayer.nondet` | `exec_prompt(prompt, *, response_format='json') -> JSONValue`; `images=` | LLM call shape | - | Not used: the contract calls `exec_prompt` in plain text mode (decision E20) |
| same | `genlayer.message` | `sender_address`, `raw` (with `datetime`) | Authorization, timestamps | - | datetime format unverified |
| same | `genlayer.types` | `Keccak256(initial_input)`, `KeccakHash.digest()/hexdigest()`, `Address` (`ZERO`, `as_bytes`, `as_hex`), `u32` etc. | Hashing and addresses | - | `digest()` return type not shown |
| same | Method dispatch guide | `gl.public.view`, `gl.public.write`; private by default | Public interface | - | - |
| same | Tail of the file (calldata / storage details / eq_principle) | **Not read** - the fetch was truncated after `nondet.web.render` | I avoided `calldata.encode` (custom canonical encoding instead) and `eq_principle` | - | Unread |
| Docs: Storage reference | whole | Use `TreeMap`/`DynArray`/sized ints; dataclass storage classes; zero-initialised defaults | Storage layout | - | Page uses **old** names (`gl.Contract`, `@allow_storage`, `gl.storage.copy_to_memory`); SDK reference is treated as authoritative. `copy_to_memory` is not used. |
| Docs: Error handling | whole | `UserError`, `VMError`, result types, error-classification pattern for consensus (LLM errors should disagree to force rotation) | Fail-closed leader error handling (E13) | - | Page uses old names (`e.message`, `run_nondet_unsafe`) |
| Docs: Transaction statuses / Transaction execution | whole | PENDING, PROPOSING, COMMITTING, REVEALING, ACCEPTED, FINALIZED, UNDETERMINED, CANCELED (+ OutOfFee); majority agreement; leader rotation; appeals can change an ACCEPTED result before FINALIZED | `FRONTEND_INTEGRATION.md` section F; consensus limitations | - | - |
| Boilerplate repository README (GitHub) | whole | Layout (`contracts/`, `tests/direct`, `tests/integration`, `gltest.config.yaml`), Python >= 3.12, commands `genvm-lint check`, `pytest tests/direct/ -v`, `gltest tests/integration/ -v -s`, cheatcodes list | Project layout and test commands | - | Repository **source files could not be fetched** (robots.txt). Boilerplate contract and config were not inspected. |
| genlayer-js / genlayer-py snippets (search results; GitHub mirrors) | partial | `waitForTransactionReceipt({status})`, `readContract({stateStatus})`, check `txExecutionResultName` | Frontend guidance | - | Secondary mirrors; confirm against official genlayer-js docs |
| **User-supplied** playbook (`GENLAYER_INTELLIGENT_CONTRACT_PLAYBOOK*.md`, two identical copies) | all | Two SDK generations; verify-before-use; run_validator with fabricated leader result; mocks first-match-wins; test-tool/runner version coupling; error classification | Process, test design, caveats | - | Playbook predates v0.4 in places |
| **User-supplied** skills + genlayer-test notes | all | Direct-mode fixtures/cheatcodes; Studio-mode `gltest` API; ACCEPTED/FINALIZED are not proof of successful execution | Test files | - | Multi-account `gltest` call style shown once; unverified |
| **User-supplied** source list + agent prompt | all | Official URLs, workflow order (lint -> direct -> integration) | Workflow | - | - |
| **User-supplied** examples (3 contracts) | all | Old-generation syntax (`from genlayer import *`, `gl.Contract`, `strict_eq`, `prompt_comparative`) | Used only as a negative reference: they are **not** valid for v0.4 and use weak comparisons | - | - |

## 1b. Sources added after the first deployment failed

| Source | What it establishes | Decision |
|--------|---------------------|----------|
| genlayerlabs/genlayer-docs issue #487 | GenVM parses the entire leading comment block as the runner JSON; extra comment lines make deployment fail with `VMError: invalid_contract`; linter and direct tests do not notice | E22, header regression tests |
| Studio announcements, 16, 18 and 23 Nov 2026 (supplied by the project owner) | v0.123 live on studio.genlayer.com on 23 Nov; new contracts must use GenVM v0.4, runner `py-genlayer:kzybg95x...`; fees required on every deploy/write; genlayer-js 2.0.0, genlayer-py 0.19.0, genlayer-test 0.30.0, CLI 0.40.0; chain ID 61999; check status **and** execution result; v0.2 support removed two weeks after the upgrade | Runner confirmed; no v0.2 build (E24); fees section in `FRONTEND_INTEGRATION.md` |
| GenVM v0.4 migration guide (https://sdk.genlayer.com/main/executors/v0.4/python-sdk/migration-guide.html) | Import pattern, `gl.contract.Contract`, `gl.storage.allow/TreeMap`, `gl.message.raw`, `UserError.data`, `run_nondet_default`, special methods must not be decorated, VM error codes (`invalid_contract runner malformed`), keccak module path `genlayer.types.keccak`, pre-finalization state named `decided` | Confirms the syntax used; E23 import chain |
| User-supplied Studio example (`LlmErc20`, header `# v0.4.0`) | Header layout, `str` address / `int` arguments, text-mode `exec_prompt`, `dict[str, int]` views | E20, E21, E22 |

Correction: earlier text in this record said the runner hash was unconfirmed and that examples
using `1jb45aa8...` were the likely target. The announcements show `kzybg95x...` is the runner for
new contracts on the production Studio since 23 Nov 2026.

## 2. Sources named by the specification that were NOT read

`full-documentation.txt`; Equivalence Principle page; Non-determinism page; Calling LLMs page;
Prompt Injection page; Testing page; skills.genlayer.com and the skills repository; protocol
architecture page; the unread tail of the SDK reference. Design choices that would normally
rest on them (prompt-injection posture, `exec_prompt` behaviour) are therefore marked unverified.

## 3. Environment inspection (Phase A)

| Item | Result |
|------|--------|
| Repository | none provided; project created from scratch; boilerplate not cloned |
| Git status | n/a (no repository) |
| Python | 3.12.3 |
| pytest / genlayer / genvm-lint / gltest / Docker / network for shell | **not available** |
| Runner configuration | `kzybg95x...`, confirmed by the 16 and 23 Nov 2026 Studio announcements; not confirmed by a linter run |

## 4. Unresolved uncertainties

See `SECURITY_AUDIT.md` section 4 and `DEPLOYMENT_READINESS.md` section 5.
