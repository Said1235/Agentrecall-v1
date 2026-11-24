# AgentRecall V1 - Deployment readiness

**No deployment was performed by the author and none is authorized.** Deployment to a public
network is for the project owner to do. Local Studio is allowed for integration tests.

## 1. Why the first delivery failed with "Could not load contract schema"

**Root cause (confirmed): the header.** GenVM reads the **whole contiguous block of leading `#`
lines** as the runner JSON (official issue genlayerlabs/genlayer-docs #487). The first delivered
file had `# { "Depends": ... }` on line 1 and more `#` comment lines directly under it, so the
block was not valid JSON. The v0.4 error code for this is `invalid_contract runner malformed`
(see the v0.4 migration guide, "VM Error Codes"); Studio surfaces it as "Could not load contract
schema". `genvm-lint` and Direct Mode tests do **not** detect it. This was the author's mistake,
not a Studio change.

**Fix.** The file now starts exactly like the Studio's own v0.4.0 example:

```
# v0.4.0
# { "Depends": "py-genlayer:kzybg95x1gn21dw72m7hyg0maaap04n4nx55j9yt6fkdqxtz6bz0" }
<blank line>
import dataclasses ...
```

Rule: nothing else may be a `#` line directly attached to those two lines. Design comments live
after the imports. `tests/harness/test_logic.py::TestDeployabilityHeader` emulates GenVM's header
read: the old file fails it ("Extra data"), the new file passes, and a mutation that glues a
comment under the runner line is detected.

**Other deployability risks removed in the same revision** (they were not proven to be failing,
but each was an unverified assumption that could also give "Could not load contract schema"):

| Risk | Change |
|------|--------|
| `Keccak256` import path never verified | try `genlayer.types`, then `genlayer.types.keccak` (module named in the migration guide), then a pure-Python Keccak-256 (verified against published vectors). The contract loads in all three cases. |
| `Address` typed public arguments | `executor` and `requester` are plain `str` hex addresses converted with `Address(...)`, exactly like the Studio's example (`to_address: str`). An AST test enforces `str` for every public argument. |
| `exec_prompt(..., response_format="json")` | plain text mode like the Studio's example; the JSON is parsed by the contract (fence-tolerant, bounded, depth-checked). |
| id-returning writes annotated `-> str` | `-> typing.Any`, as in the official PredictionMarket example. |

## 2. Which Studio and runner

Official announcements supplied by the project owner:

- 16 Nov 2026: Studio Next replaced GenVM v0.3 with v0.4; new deployments must use v0.4.
- 23 Nov 2026: **Studio v0.123 is live at https://studio.genlayer.com.** Use GenVM v0.4 for new
  contracts; runner `py-genlayer:kzybg95x1gn21dw72m7hyg0maaap04n4nx55j9yt6fkdqxtz6bz0`.
  Existing v0.2 contracts keep working for now; v0.2 support will be removed two weeks later.

So the contract's runner is the officially announced v0.4 runner. (`py-genlayer-multi:ys9w7shpvsdswe2fhrxh7agke954catkqb28cngq5924zw9bzx80`
is for multi-file contracts; this project is a single file.) There is no v0.2 build: it is not
needed for new contracts and would stop working soon.

## 3. Artifact

| Item | Value |
|------|-------|
| Contract source | `contracts/agent_recall.py` (single file) |
| Contract class | `AgentRecall(gl.contract.Contract)` |
| Constructor | `__init__(self)` - **no arguments**, no configuration, no secrets |
| External requirements | none: no API keys, no LLM provider key, no server, database, backend, registry or URL |
| Imports | `dataclasses`, `json`, `typing`, `genlayer`, `genlayer.types` |

## 4. Deploy and troubleshoot

0. **Bisect tool:** first deploy `contracts/smoke_test.py` (same header, imports and storage building blocks, 40 lines). If it deploys but `agent_recall.py` does not, the problem is inside `agent_recall.py`; if it also fails, it is the header/runner/Studio environment.
1. Open https://studio.genlayer.com, create a new contract, paste the **entire** content of
   `contracts/agent_recall.py` (it must start with `# v0.4.0`), deploy with no constructor
   arguments. The Studio UI attaches fees automatically; with the CLI or SDKs, estimate fees
   first (genlayer-js 2.0.0 / genlayer-py 0.19.0 / CLI 0.40.0) and pass them with every deploy
   and write.
2. After every transaction check **both** the status and the execution result.
3. Chain ID is 61999 on studio.genlayer.com (61997 on Studio Next); if you send several
   transactions from one account, wait for each submission to return before signing the next.

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| "Could not load contract schema" / `invalid_contract runner malformed` | text pasted above/below the header, extra `#` lines glued to the runner line, or a stray character | paste the file unchanged; first line `# v0.4.0`, second line the `Depends` JSON, third line blank |
| `invalid_contract runner absent` | no runner comment | same |
| Same message but the header is intact | an import or schema problem the harness cannot see | copy the **exact** receipt / stderr text and report it; do not retry blindly |
| `FeesDistributionMissing`, `FeeValueMustBeNonZero` | fees not attached (SDK/CLI/test tooling) | estimate fees and pass them |
| Contract reverts with `[EXPECTED] ...` | contract business rule | see `FRONTEND_INTEGRATION.md` section H |

## 5. Pre-deployment checklist

1. `pip install genvm-linter genlayer-test==0.30.0` and `npm install -g genlayer@0.40.0` (stable versions announced on 23 Nov 2026; match your local Studio if you run one).
2. `genvm-lint check contracts/agent_recall.py --json`. The linter does not catch the header bug; the harness does.
3. `python3 -m unittest discover -s tests/harness -v` (logic harness).
4. `pytest tests/direct/ -v`.
5. Deploy and run `gltest tests/integration/ -v -s` against the Studio **you are authorized to use**.
6. Resolve `SECURITY_AUDIT.md` F2 (evaluate all criteria vs only disputed) with the project owner.

## 6. Known unverified items

Schema loading on the real toolchain (beyond the header); storage dataclass construction with
`Address` / `u32` fields; `gl.message.raw["datetime"]` format; `exec_prompt` text output on real
validators; closure serialization in `run_nondet_default`; validator behaviour when `validator_fn`
returns `False` for a leader error; LLM context limits at the largest input (~37 KB of prompt
data); `genlayer-test` mock and `run_validator` details; whether `genlayer-test` 0.30.0 attaches fees.
