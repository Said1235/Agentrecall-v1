"""Meta-check: the independent audit harness must FAIL on deliberately broken copies of the contract."""
import os, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
HARNESS = os.path.join(HERE, "audit_harness.py")
MUT = os.path.join(tempfile.mkdtemp(prefix="agentrecall_mutant_"), "repo")
SCRATCH = tempfile.mkdtemp(prefix="agentrecall_evidence_")
mutations = {
 "validator ignores per-criterion outcome mismatch": ('if mine["criterion_id"] != theirs["criterion_id"] or mine["outcome"] != theirs["outcome"]:\n                        return False', 'pass'),
 "validator skips claim verification": ("return _verify_claims(ctx, proposed)", "return True"),
 "validator accepts leader errors": ("# Leader error (LLM_ERROR, VM error, ...): never lock in a technical failure.\n                return False", "return True"),
 "challenge open to anyone": ('if gl.message.sender_address != c.requester:\n            _fail("UNAUTHORIZED", "only the requester can challenge")', "pass"),
 "adjudicate ignores lifecycle state": ("        c = self._commitment(commitment_id)\n        self._require_status(commitment_id, STATUS_CHALLENGED)\n\n        sid", "        c = self._commitment(commitment_id)\n\n        sid"),
 "submission content hash not verified": ('if _content_hash(commitment_id, content) != s.content_hash:\n            _fail("HASH_MISMATCH", "submission content")', "pass"),
 "challenge material hash not verified": ('if _challenge_hash(sid, ch.requester.as_bytes, statement, disputed, ch_evidence) != ch.challenge_hash:\n            _fail("HASH_MISMATCH", "challenge material")', "pass"),
 "second adjudication overwrites": ('        if aid in self.adjudications:\n            _fail("ALREADY_EXISTS", "adjudication")\n', ""),
 "overall verdict not checked against criteria": ("or overall != _derive_overall(canonical):", ":"),
 "persist before consensus (write above nondet block)": ("        proposal = gl.vm.run_nondet_default(leader_fn, validator_fn)", "        self.commitment_status[commitment_id] = STATUS_ADJUDICATED\n        proposal = gl.vm.run_nondet_default(leader_fn, validator_fn)"),
 "storage touched inside leader_fn": ("                results = _evaluate(ctx)\n            except Exception:", "                self.commitment_status[commitment_id]\n                results = _evaluate(ctx)\n            except Exception:"),
 "failed call leaves partial state (status set before validation)": ("        self._require_status(commitment_id, STATUS_ACCEPTED)\n\n        kinds = json.loads(c.accepted_kinds_json)", "        self._require_status(commitment_id, STATUS_ACCEPTED)\n        self.commitment_status[commitment_id] = STATUS_SUBMITTED\n\n        kinds = json.loads(c.accepted_kinds_json)"),
 "unexpected exception type escapes (no id type check)": ('        if not isinstance(commitment_id, str) or commitment_id not in self.commitments:\n            _fail("NOT_FOUND", "commitment")', '        if commitment_id not in self.commitments:\n            _fail("NOT_FOUND", "commitment")'),
 "challenge may be replayed (state check removed)": ("        self._require_status(commitment_id, STATUS_SUBMITTED)\n\n        criteria = json.loads(c.criteria_json)", "        criteria = json.loads(c.criteria_json)"),
 "evidence ids from other namespaces unchecked": ("if not isinstance(eid, str) or eid not in kinds:", "if not isinstance(eid, str):"),
 "terminal state reopenable (cancel allowed after accept)": ('        self._require_status(commitment_id, STATUS_OPEN)\n        self.commitment_status[commitment_id] = STATUS_CANCELLED', '        self.commitment_status[commitment_id] = STATUS_CANCELLED'),
}
base = subprocess.run([sys.executable, HARNESS], capture_output=True, text=True, env=dict(os.environ, AGENTRECALL_REPO=REPO, AUDIT_EVIDENCE_DIR=SCRATCH))
assert base.returncode == 0, "baseline must pass:\n" + base.stderr[-500:]
print("baseline: audit harness passes against the real contract")
survivors = []
for name, (old, new) in mutations.items():
    shutil.rmtree(MUT, ignore_errors=True)
    os.makedirs(os.path.dirname(MUT), exist_ok=True)
    shutil.copytree(REPO, MUT, ignore=shutil.ignore_patterns(".git", "__pycache__", "audit"))
    p = MUT + "/contracts/agent_recall.py"
    s = open(p).read()
    if old not in s:
        print("TARGET NOT FOUND:", name); sys.exit(1)
    open(p, "w").write(s.replace(old, new, 1))
    r = subprocess.run([sys.executable, HARNESS], capture_output=True, text=True, env=dict(os.environ, AGENTRECALL_REPO=MUT, AUDIT_EVIDENCE_DIR=SCRATCH))
    killed = r.returncode != 0
    print(("DETECTED " if killed else "SURVIVED "), name)
    if not killed: survivors.append(name)
shutil.rmtree(MUT, ignore_errors=True)
print("survivors:", survivors)
# AR-09: removing the unreachable ALREADY_EXISTS guard changes no behaviour (equivalent mutant).
EXPECTED_SURVIVORS = {"second adjudication overwrites"}
sys.exit(0 if set(survivors) == EXPECTED_SURVIVORS else 1)
