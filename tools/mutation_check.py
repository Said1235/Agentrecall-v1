import subprocess, shutil, os, sys
SRC = "contracts/agent_recall.py"  # run from the repository root
orig = open(SRC).read()
mutations = {
 "comment glued under runner line (the real deploy bug)": ("}\n\nimport dataclasses", "}\n# glued comment\nimport dataclasses"),
 "address-typed public argument": ("        executor: str,\n        description: str,", "        executor: Address,\n        description: str,"),
 "decorated __init__ (forbidden in v0.4)": ("    def __init__(self):", "    @gl.public.write\n    def __init__(self):"),
 "json response_format reintroduced": ("gl.nondet.exec_prompt(_build_eval_prompt(ctx))", "gl.nondet.exec_prompt(_build_eval_prompt(ctx), response_format=\"json\")"),
 "keccak fallback broken (wrong padding)": ("def _keccak256_pure(data: bytes, pad_byte: int = 0x01)", "def _keccak256_pure(data: bytes, pad_byte: int = 0x06)"),

 "validator skips claim verification": ("return _verify_claims(ctx, proposed)", "return True"),
 "validator skips independent outcome comparison": ("if mine[\"criterion_id\"] != theirs[\"criterion_id\"] or mine[\"outcome\"] != theirs[\"outcome\"]:\n                        return False", "pass"),
 "validator accepts leader errors": ("# Leader error (LLM_ERROR, VM error, ...): never lock in a technical failure.\n                return False", "return True"),
 "no content hash check at adjudication": ("if _content_hash(commitment_id, content) != s.content_hash:\n            _fail(\"HASH_MISMATCH\", \"submission content\")", "pass"),
 "MET may rest on external reference": ("if outcome == \"MET\" and not any(kinds[eid] != KIND_EXTERNAL for eid in cited):", "if False:"),
 "overall not derived consistently": ("or overall != _derive_overall(canonical):", ":"),
 "evidence ids not checked against package": ("if not isinstance(eid, str) or eid not in kinds:", "if not isinstance(eid, str):"),
 "ids not compared (package hash)": ("for key in (\"commitment_id\", \"submission_id\", \"challenge_id\", \"evidence_package_hash\"):", "for key in ():"),
 "anyone can accept": ("if gl.message.sender_address != c.executor:\n            _fail(\"UNAUTHORIZED\", \"only the executor can accept\")", "pass"),
 "challenge allowed in wrong state": ("self._require_status(commitment_id, STATUS_SUBMITTED)\n\n        criteria = json.loads(c.criteria_json)", "criteria = json.loads(c.criteria_json)"),
 "no domain separation": ("_enc_into(buf, HASH_DOMAIN_PREFIX + domain)", "pass"),
 "duplicate evidence content allowed": ("if (kind, content) in seen_content:", "if False:"),
 "no depth guard": ("if not _json_depth_ok(text, MAX_JSON_DEPTH):", "if False:"),
 "persist even if status check skipped": ("self._require_status(commitment_id, STATUS_CHALLENGED)\n\n        sid", "sid"),
}
base = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests/harness"], capture_output=True, text=True)
assert base.returncode == 0, "BASELINE FAILS - mutation results would be meaningless:\n" + base.stderr[-800:]
print("baseline OK")
survived = []
for name, (old, new) in mutations.items():
    if old not in orig:
        print("MUTATION TARGET NOT FOUND:", name); sys.exit(1)
    open(SRC, "w").write(orig.replace(old, new, 1))
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests/harness"], capture_output=True, text=True)
    killed = r.returncode != 0
    print(("KILLED  " if killed else "SURVIVED"), name)
    if not killed: survived.append(name)
open(SRC, "w").write(orig)
print("survivors:", survived)
sys.exit(0 if not survived else 1)
