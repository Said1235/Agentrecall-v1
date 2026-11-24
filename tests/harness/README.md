# Logic harness (development only)

`stub/genlayer/` is a **hand-written, minimal stand-in** for the `genlayer` package. It exposes
only the names the contract uses (verified in the v0.4.0-rc1 API reference) so that
`contracts/agent_recall.py` can run in plain CPython.

It is **not** the SDK and **not** GenVM:
- `Keccak256` is SHA3-256 (different padding from Keccak-256).
- `run_nondet_default` runs the leader and then calls the validator once, in-process.
- Storage is a Python dict; there is no serialization, no sandbox, no gas, no consensus.

What it proves: the contract's own logic. What it does not prove: anything about the real SDK,
linter, runner, LLMs, validators or consensus.

```
python3 -m unittest discover -s tests/harness -v
python3 tools/mutation_check.py
```

It also contains `TestDeployabilityHeader`, which emulates how GenVM reads the runner header. A harness
cannot prove a contract deploys; this check only guards against the specific header mistake that
broke the first delivery.

Requires only Python 3.12+. Do not copy `stub/` into a real GenLayer project.
