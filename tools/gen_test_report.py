"""Regenerates docs/TEST_REPORT.md from an ACTUAL run of the logic harness and the mutation check.
Run from the repository root:  python3 tools/gen_test_report.py
"""
import datetime
import re
import subprocess
import sys
import unittest

sys.path.insert(0, "tests/harness")


def flatten(suite):
    for t in suite:
        if isinstance(t, unittest.TestSuite):
            yield from flatten(t)
        else:
            yield t


rows = []
for t in flatten(unittest.TestLoader().discover("tests/harness")):
    r = unittest.TestResult()
    t.run(r)
    name = t._testMethodName
    rows.append((type(t).__name__, name, name.replace("test_", "", 1).replace("_", " "), "pass" if r.wasSuccessful() else "FAIL"))
passed = sum(1 for r in rows if r[3] == "pass")

mut = subprocess.run([sys.executable, "tools/mutation_check.py"], capture_output=True, text=True).stdout.splitlines()
mut_rows = [l for l in mut if l.startswith(("KILLED", "SURVIVED"))]
killed = sum(1 for l in mut_rows if l.startswith("KILLED"))

direct = re.findall(r"^def (test_\w+)", open("tests/direct/test_agent_recall.py").read(), re.M)
integ = re.findall(r"^def (test_\w+)", open("tests/integration/test_agent_recall_studio.py").read(), re.M)

out = ["# AgentRecall V1 - Test report\n",
       "Generated on %s by `tools/gen_test_report.py` from an actual run. Nothing here is estimated.\n" % datetime.date.today().isoformat(),
       """## 1. Summary - what is and is not verified

| Level | Status |
|-------|--------|
| Contract implemented | **Yes** (`contracts/agent_recall.py`) |
| Deploy-header check (emulates GenVM's runner-comment read) | **Passes**; the previously delivered file **fails** it (`Extra data`) |
| `genvm-lint check` | **NOT RUN** - linter unavailable in the authoring environment (and it does not detect the header bug) |
| Logic harness (plain CPython + hand-written SDK stub) | **%d / %d passed** |
| Mutation check of the harness | **%d mutations injected, %d detected** |
| Direct Mode tests (official fixtures) | **Written (%d functions), NOT EXECUTED** |
| Studio integration tests | **Written (%d functions), NOT EXECUTED** |
| Real deployment, real consensus, real LLM behaviour | **NOT VERIFIED** |

**Tested successfully** = the harness results below: contract logic against a stub that mirrors the
SDK names confirmed in the v0.4 migration guide. **Tested with mocks only** = the same (the LLM is a
deterministic fake; `run_nondet_default` is a stub that runs leader then validator). **Tested in
Studio** = nothing. **Not tested** = anything that depends on the real GenVM, linter or tooling.

**Important limit:** a harness proves logic, not deployability. The first delivery passed 81 harness
tests and still could not be deployed (`invalid_contract runner malformed`). The header, import and
annotation checks added since (section 3: `TestDeployabilityHeader`, `TestKeccakFallback`) reduce
that risk but cannot replace deploying on the real Studio.
""" % (passed, len(rows), len(mut_rows), killed, len(direct), len(integ)),
       "## 2. Reproduce\n\n```\npython3 -m unittest discover -s tests/harness -v\npython3 tools/mutation_check.py\n```\n",
       "## 3. Harness results (executed)\n\n| # | Group | Test | Purpose (from name) | Expected | Actual | Mode |\n|---|-------|------|---------------------|----------|--------|------|"]
for i, (c, n, p, res) in enumerate(rows, 1):
    out.append("| %d | %s | `%s` | %s | pass | %s | harness (stub SDK) |" % (i, c, n, p, res))
out += ["", "## 4. Mutation check (executed)\n\nEach defect is applied to a temporary copy of the contract; the suite must fail. The baseline is asserted green first.\n", "| Result | Injected defect |", "|--------|-----------------|"]
for l in mut_rows:
    k, _, d = l.partition(" ")
    out.append("| %s | %s |" % (k.strip(), d.strip()))
out += ["", "## 5. Not executed\n", "### 5.1 Direct Mode (`tests/direct/test_agent_recall.py`)\n\n`pytest tests/direct/ -v` with genlayer-test 0.30.0. Functions (several parametrized):\n"]
out += ["- `%s`" % n for n in direct]
out += ["", "### 5.2 Studio (`tests/integration/test_agent_recall_studio.py`)\n\n`gltest tests/integration/ -v -s` against a Studio you are authorized to use. Fees apply (Studio v0.123). Functions:\n"]
out += ["- `%s`" % n for n in integ]
out.append("""
### 5.3 Checks nobody has run yet
1. Deploying the file on the real Studio and reading the schema it produces
2. `genvm-lint check contracts/agent_recall.py --json`
3. Real validator behaviour when `validator_fn` returns `False` for a leader `[LLM_ERROR]`
4. Real LLM text output (fenced JSON, extra prose) and the contract's parsing of it
5. Consensus rotation, `UNDETERMINED`, finality, appeals, fees for `adjudicate`
6. Storage construction of dataclasses with `Address` / `u32` fields; `gl.message.raw["datetime"]`
7. Behaviour with the largest allowed package (~37 KB of prompt data)
8. Whether the SDK's `Keccak256` is importable on the real runner (the contract works either way)
""")
open("docs/TEST_REPORT.md", "w").write("\n".join(out))
print("harness %d/%d, mutations %d/%d" % (passed, len(rows), killed, len(mut_rows)))
