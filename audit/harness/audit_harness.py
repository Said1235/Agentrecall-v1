"""AgentRecall V1 - independent adversarial audit harness.

READ-ONLY with respect to the audited repository: it imports the contract by path and never
writes to it. It runs the contract in plain CPython against the dev-only SDK stub that ships in
the repo (tests/harness/stub). It therefore audits CONTRACT LOGIC. It cannot audit the real
GenVM, real storage, real LLMs or real consensus (see the reports for what stays unverified).

Run (from the repository root):  python3 audit/harness/audit_harness.py [-v]
Statistics for the reports are written to audit/evidence/stats.json.
"""

import ast
import copy
import importlib.util
import json
import os
import pickle
import random
import re
import sys
import time
import unicodedata
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("AGENTRECALL_REPO", os.path.abspath(os.path.join(HERE, "..", "..")))
EVIDENCE = os.environ.get("AUDIT_EVIDENCE_DIR", os.path.abspath(os.path.join(HERE, "..", "evidence")))
CONTRACT_PATH = os.path.join(REPO, "contracts", "agent_recall.py")
sys.path.insert(0, os.path.join(REPO, "tests", "harness", "stub"))

import genlayer as gl  # noqa: E402  (dev stub)
from genlayer.types import Address  # noqa: E402

_spec = importlib.util.spec_from_file_location("agent_recall", CONTRACT_PATH)
ar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ar)

with open(CONTRACT_PATH, encoding="utf-8") as _fh:
    SOURCE = _fh.read()

STATS = {}

REQ = Address("0x" + "11" * 20)
EXE = Address("0x" + "22" * 20)
OTH = Address("0x" + "33" * 20)
REQ2 = Address("0x" + "44" * 20)

CRITERIA3 = [
    {"id": "C1", "text": "The report lists exactly three risks"},
    {"id": "C2", "text": "The report is shorter than 500 words"},
    {"id": "C3", "text": "The report names an owner for each risk"},
]
KINDS = ["TEXT", "STRUCTURED", "CONTENT_HASH", "ARTIFACT", "EXTERNAL_REFERENCE"]
CONTENT = "Risks: 1) delay 2) cost 3) scope. Word count: 120."
EVID = [
    {"id": "E1", "kind": "TEXT", "content": "Draft word count is 120"},
    {"id": "E2", "kind": "EXTERNAL_REFERENCE", "content": "https://example.com/report"},
]
STATEMENT = "Only two risks are listed in the report"
DISPUTED = ["C1"]
CH_EVID = [{"id": "X1", "kind": "TEXT", "content": "Report lists delay and cost only"}]


def j(x):
    return json.dumps(x)


def res(cid, outcome, reasons=None, cited=None):
    dr = {"MET": "EVIDENCE_SUFFICIENT", "NOT_MET": "DELIVERY_INCOMPLETE", "INDETERMINATE": "EVIDENCE_INSUFFICIENT"}
    dc = {"MET": ["S:#DELIVERY", "S:E1"], "NOT_MET": ["S:#DELIVERY"], "INDETERMINATE": []}
    return {
        "criterion_id": cid,
        "outcome": outcome,
        "reason_codes": reasons if reasons is not None else [dr[outcome]],
        "evidence_ids": cited if cited is not None else dc[outcome],
    }


def install_llm(outcomes, verify="SUPPORTED", ids=("C1", "C2", "C3")):
    def responder(prompt):
        if "ROLE: EVALUATOR" in prompt:
            return {"criteria_results": [res(c, o) for c, o in outcomes.items()]}
        if "ROLE: VERIFIER" in prompt:
            return {"verdicts": [{"criterion_id": c, "verdict": verify if isinstance(verify, str) else verify[c]} for c in ids]}
        raise AssertionError("unexpected prompt")

    gl.nondet.responder = responder


def snapshot(c):
    return {n: {k: repr(v) for k, v in getattr(c, n).items()} for n in ("commitments", "commitment_status", "submissions", "challenges", "adjudications")}


class Env:
    """Fresh contract + helpers."""

    def __init__(self, criteria=None):
        self.c = ar.AgentRecall()
        self.criteria = criteria or CRITERIA3
        gl.nondet.responder = None
        gl.vm.state.llm_calls = 0
        gl.vm.state.last = None

    def as_(self, who):
        gl.message.sender_address = who

    def create(self, nonce="n1", requester=REQ, executor=EXE):
        self.as_(requester)
        return self.c.create_commitment(nonce, executor.as_hex, "Deliver a risk report", j(self.criteria), j(KINDS))

    def accepted(self, nonce="n1", requester=REQ, executor=EXE):
        cid = self.create(nonce, requester, executor)
        self.as_(executor)
        self.c.accept_commitment(cid)
        return cid

    def submitted(self, nonce="n1", requester=REQ, executor=EXE, content=CONTENT, evid=EVID):
        cid = self.accepted(nonce, requester, executor)
        self.as_(executor)
        self.c.submit_delivery(cid, content, j(evid))
        return cid

    def challenged(self, nonce="n1", requester=REQ, executor=EXE, content=CONTENT, evid=EVID, statement=STATEMENT, ch_evid=CH_EVID):
        cid = self.submitted(nonce, requester, executor, content, evid)
        self.as_(requester)
        self.c.create_challenge(cid, statement, j(DISPUTED), j(ch_evid))
        return cid

    def adjudicate(self, cid, who=OTH, content=CONTENT, evid=EVID, statement=STATEMENT, disputed=DISPUTED, ch_evid=CH_EVID):
        self.as_(who)
        return self.c.adjudicate(cid, content, j(evid), statement, j(disputed), j(ch_evid))

    def status(self, cid):
        return self.c.get_commitment(cid)["status"]


def is_user_error(exc):
    return isinstance(exc, gl.vm.UserError)


# =============================================================================================
class A1_TypeConfusionAndAtomicity(unittest.TestCase):
    """Every public method with hostile argument values: only controlled UserErrors, and a failed
    call must leave the whole contract state byte-for-byte unchanged."""

    POOL = [None, 0, 1, -1, 2 ** 70, 1.5, True, False, "", " ", "x", "a" * 70000, "\x00", "\ud800", "0x" + "00" * 20,
            "0x" + "zz" * 20, "0x" + "11" * 20, [], ["a"], {}, {"a": 1}, b"raw", (1, 2)]

    def builders(self):
        def fresh(env):
            return None

        return {
            "create_commitment": (lambda e: (None, REQ), lambda e, cid: ["n9", EXE.as_hex, "d", j(CRITERIA3), j(KINDS)]),
            "accept_commitment": (lambda e: (e.create(), EXE), lambda e, cid: [cid]),
            "reject_commitment": (lambda e: (e.create(), EXE), lambda e, cid: [cid]),
            "cancel_commitment": (lambda e: (e.create(), REQ), lambda e, cid: [cid]),
            "submit_delivery": (lambda e: (e.accepted(), EXE), lambda e, cid: [cid, CONTENT, j(EVID)]),
            "create_challenge": (lambda e: (e.submitted(), REQ), lambda e, cid: [cid, STATEMENT, j(DISPUTED), j(CH_EVID)]),
            "close_uncontested": (lambda e: (e.submitted(), REQ), lambda e, cid: [cid]),
            "adjudicate": (lambda e: (e.challenged(), OTH), lambda e, cid: [cid, CONTENT, j(EVID), STATEMENT, j(DISPUTED), j(CH_EVID)]),
            "compute_commitment_id": (lambda e: (None, REQ), lambda e, cid: [REQ.as_hex, "n1"]),
            "get_commitment": (lambda e: (e.create(), REQ), lambda e, cid: [cid]),
            "get_submission": (lambda e: (e.submitted(), REQ), lambda e, cid: [ar._submission_id(cid)]),
            "get_challenge": (lambda e: (e.challenged(), REQ), lambda e, cid: [ar._challenge_id(ar._submission_id(cid))]),
            "get_adjudication": (lambda e: (e.challenged(), REQ), lambda e, cid: ["00" * 32]),
        }

    def test_hostile_arguments(self):
        unexpected = []
        accepted_weird = []
        calls = 0
        for method, (prep, argsf) in self.builders().items():
            probe = Env()
            install_llm({"C1": "MET", "C2": "NOT_MET", "C3": "INDETERMINATE"})
            cid, who = prep(probe)
            nparams = len(argsf(probe, cid))
            for idx in range(nparams):
                for val in self.POOL:
                    env = Env()
                    install_llm({"C1": "MET", "C2": "NOT_MET", "C3": "INDETERMINATE"})
                    cid, who = prep(env)
                    args = argsf(env, cid)
                    args[idx] = val
                    env.as_(who)
                    before = snapshot(env.c)
                    calls += 1
                    try:
                        getattr(env.c, method)(*args)
                        ok = True
                    except Exception as exc:  # noqa: BLE001
                        ok = False
                        if not is_user_error(exc) and not isinstance(exc, gl.ConsensusDisagreement):
                            unexpected.append((method, idx, repr(val)[:30], type(exc).__name__, str(exc)[:80]))
                    after = snapshot(env.c)
                    if not ok:
                        self.assertEqual(before, after, "failed call mutated state: %s arg %d %r" % (method, idx, val))
                    elif not method.startswith(("get_", "compute_")):
                        accepted_weird.append((method, idx, repr(val)[:40]))
        non_string = [x for x in accepted_weird if not x[2].startswith("'")]
        STATS["A1_non_string_values_accepted_by_writes"] = non_string
        self.assertEqual(non_string, [], "a write accepted a non-string argument")
        STATS["A1_calls"] = calls
        STATS["A1_unexpected_exception_types"] = unexpected
        STATS["A1_weird_values_accepted_by_writes"] = accepted_weird
        self.assertEqual(unexpected, [], "non-UserError exceptions escaped: %r" % unexpected[:5])


# =============================================================================================
class A2_ModelBasedRandomWalk(unittest.TestCase):
    """Independent reference model of the lifecycle; random operations by random actors against
    several commitments; contract must agree with the model after every step and records must
    never change after creation."""

    ACTORS = [REQ, EXE, OTH, REQ2]
    NONCES = ["a", "b", "c", "d"]

    def run_walk(self, seed, steps):
        rnd = random.Random(seed)
        env = Env()
        model = {}      # cid -> dict(status, req, exe)
        created = []
        record_repr = {}
        counters = {"ok": 0, "err": 0, "consensus_fail": 0}
        per_op = {}
        broken_llm = lambda p: (_ for _ in ()).throw(RuntimeError("llm down"))  # noqa: E731
        for step in range(steps):
            op = rnd.choice(["create", "accept", "reject", "cancel", "submit", "challenge", "close", "adjudicate"])
            actor = rnd.choice(self.ACTORS)
            cid = None
            if created and rnd.random() < 0.65:  # guided: push an existing commitment one step forward
                cid = rnd.choice(created)
                nxt = {"OPEN": ["accept", "accept", "reject", "cancel"], "ACCEPTED": ["submit"], "SUBMITTED": ["challenge", "challenge", "close"],
                       "CHALLENGED": ["adjudicate"]}.get(model[cid]["status"])
                if nxt:
                    op = rnd.choice(nxt)
                    if rnd.random() < 0.8:
                        m_ = model[cid]
                        actor = m_["exe"] if op in ("accept", "reject", "submit") else (m_["req"] if op in ("cancel", "challenge", "close") else actor)
            env.as_(actor)
            corrupt = rnd.random() < 0.12
            fake = rnd.random() < 0.05
            if cid is None or fake:
                cid = "00" * 32 if (fake or not created) else rnd.choice(created)
            use_broken = op == "adjudicate" and rnd.random() < 0.25
            if use_broken:
                gl.nondet.responder = broken_llm
            else:
                install_llm({"C1": rnd.choice(["MET", "NOT_MET", "INDETERMINATE"]), "C2": "MET", "C3": rnd.choice(["MET", "NOT_MET"])})
            before = snapshot(env.c)
            expected = None  # None = success, else error code or "CONSENSUS"
            new_cid = None
            if op == "create":
                nonce = rnd.choice(self.NONCES)
                executor = rnd.choice([EXE, EXE, OTH, actor])
                new_cid = ar._commitment_id(actor.as_bytes, nonce)
                if executor == actor:
                    expected = "INVALID_INPUT"
                elif new_cid in model:
                    expected = "ALREADY_EXISTS"
                call = lambda: env.c.create_commitment(nonce, executor.as_hex, "d", j(CRITERIA3), j(KINDS))  # noqa: E731
                exe_for_model = executor
            else:
                if cid not in model:
                    expected = "NOT_FOUND"
                else:
                    m = model[cid]
                    need = {"accept": ("exe", "OPEN"), "reject": ("exe", "OPEN"), "cancel": ("req", "OPEN"),
                            "submit": ("exe", "ACCEPTED"), "challenge": ("req", "SUBMITTED"),
                            "close": ("req", "SUBMITTED"), "adjudicate": (None, "CHALLENGED")}[op]
                    who, status = need
                    if who == "exe" and actor != m["exe"]:
                        expected = "UNAUTHORIZED"
                    elif who == "req" and actor != m["req"]:
                        expected = "UNAUTHORIZED"
                    elif m["status"] != status:
                        expected = "INVALID_STATE"
                    elif corrupt and op in ("submit", "challenge", "adjudicate"):
                        expected = "ANY"  # deterministic input/hash checks run before any LLM call
                    elif use_broken:
                        expected = "CONSENSUS"
                if op == "accept":
                    call = lambda: env.c.accept_commitment(cid)  # noqa: E731
                elif op == "reject":
                    call = lambda: env.c.reject_commitment(cid)  # noqa: E731
                elif op == "cancel":
                    call = lambda: env.c.cancel_commitment(cid)  # noqa: E731
                elif op == "submit":
                    call = lambda: env.c.submit_delivery(cid, "" if corrupt else CONTENT, j(EVID))  # noqa: E731
                elif op == "challenge":
                    call = lambda: env.c.create_challenge(cid, "" if corrupt else STATEMENT, j(DISPUTED), j(CH_EVID))  # noqa: E731
                elif op == "close":
                    call = lambda: env.c.close_uncontested(cid)  # noqa: E731
                else:
                    call = lambda: env.c.adjudicate(cid, CONTENT + ("x" if corrupt else ""), j(EVID), STATEMENT, j(DISPUTED), j(CH_EVID))  # noqa: E731
            per_op.setdefault(op, {"ok": 0, "err": 0})
            try:
                call()
                outcome = "ok"
                err = None
            except gl.ConsensusDisagreement:
                outcome, err = "consensus", "CONSENSUS"
            except gl.vm.UserError as exc:
                outcome = "err"
                m_ = re.match(r"\[(?:EXPECTED|LLM_ERROR)\] ?([A-Z_]*)", str(exc.data))
                err = m_.group(1) if m_ else str(exc.data)
            if expected is None:
                self.assertEqual(outcome, "ok", "step %d %s by %s on %s: expected success, got %s" % (step, op, actor, cid[:8], err))
            elif expected == "ANY":
                self.assertNotEqual(outcome, "ok", "step %d corrupt %s accepted" % (step, op))
            elif expected == "CONSENSUS":
                self.assertEqual(outcome, "consensus", "step %d %s" % (step, op))
            else:
                self.assertEqual(err, expected, "step %d %s by %s: expected %s got %s/%s" % (step, op, actor, expected, outcome, err))
            if outcome == "ok":
                counters["ok"] += 1
                per_op[op]["ok"] += 1
                if op == "create":
                    created.append(new_cid)
                    model[new_cid] = {"status": "OPEN", "req": actor, "exe": exe_for_model}
                    record_repr[new_cid] = repr(env.c.commitments[new_cid])
                else:
                    model[cid]["status"] = {"accept": "ACCEPTED", "reject": "REJECTED", "cancel": "CANCELLED", "submit": "SUBMITTED",
                                            "challenge": "CHALLENGED", "close": "UNCONTESTED", "adjudicate": "ADJUDICATED"}[op]
            else:
                counters["consensus_fail" if outcome == "consensus" else "err"] += 1
                per_op[op]["err"] += 1
                self.assertEqual(before, snapshot(env.c), "failed step %d (%s) mutated state" % (step, op))
            # global invariants after every step
            for k, m in model.items():
                self.assertEqual(env.status(k), m["status"], "status drift on %s" % k[:8])
                self.assertEqual(repr(env.c.commitments[k]), record_repr[k], "commitment record mutated")
            self.assertEqual(set(env.c.commitment_status), set(model))
        return counters, per_op

    def test_random_walks(self):
        total = {"ok": 0, "err": 0, "consensus_fail": 0}
        ops = {}
        for seed in range(40):
            c, p = self.run_walk(seed, 500)
            for k in total:
                total[k] += c[k]
            for op, v in p.items():
                o = ops.setdefault(op, {"ok": 0, "err": 0})
                o["ok"] += v["ok"]
                o["err"] += v["err"]
        STATS["A2_steps"] = 40 * 500
        STATS["A2_totals"] = total
        STATS["A2_per_operation"] = ops
        for op in ("create", "accept", "reject", "cancel", "submit", "challenge", "close", "adjudicate"):
            self.assertGreater(ops[op]["ok"], 0, "walk never exercised a successful %s" % op)
            self.assertGreater(ops[op]["err"], 0, "walk never exercised a failing %s" % op)
        self.assertGreater(total["consensus_fail"], 0, "walk never exercised a failed consensus")


# =============================================================================================
class A3_ValidatorMutationFuzz(unittest.TestCase):
    """Mutation-fuzz the leader proposal. Any ACCEPTED mutation must be immaterial (identical
    decision-critical view). Immaterial differences (reason codes / evidence ids) are counted:
    they quantify the by-design weakness 'E9'."""

    def setUp(self):
        self.env = Env()
        cid = self.env.challenged()
        install_llm({"C1": "MET", "C2": "NOT_MET", "C3": "INDETERMINATE"})
        self.env.adjudicate(cid)
        self.leader_fn, self.validator_fn = gl.vm.state.last
        self.honest = self.leader_fn()
        self.honest_snapshot = copy.deepcopy(self.honest)

    @staticmethod
    def material(p):
        if not isinstance(p, dict):
            return ("NOT_DICT",)
        try:
            return (p["schema_version"], type(p["schema_version"]).__name__, p["commitment_id"], p["submission_id"], p["challenge_id"],
                    p["evidence_package_hash"], p["overall_outcome"],
                    tuple((r["criterion_id"], r["outcome"]) for r in p["criteria_results"]))
        except Exception:  # noqa: BLE001
            return ("BROKEN",)

    VALID_IDS = {"S:#DELIVERY", "S:E1", "S:E2", "C:X1"}
    EXTERNAL_IDS = {"S:E2"}
    REASONS = {"MET": {"EVIDENCE_SUFFICIENT"},
               "NOT_MET": {"EVIDENCE_CONTRADICTS", "REQUIREMENT_NOT_ADDRESSED", "DELIVERY_INCOMPLETE"},
               "INDETERMINATE": {"EVIDENCE_INSUFFICIENT", "EVIDENCE_AMBIGUOUS", "EVIDENCE_CONFLICTING", "UNVERIFIABLE_CLAIM"}}

    def structural_violations(self, p):
        """INDEPENDENT oracle (does not reuse the contract's validators) for the structural invariants
        every accepted proposal must satisfy."""
        bad = []
        if set(p) != {"schema_version", "commitment_id", "submission_id", "challenge_id", "evidence_package_hash", "overall_outcome", "criteria_results"}:
            bad.append("keys")
        rs = p["criteria_results"]
        if [r["criterion_id"] for r in rs] != ["C1", "C2", "C3"]:
            bad.append("criterion set/order")
        for r in rs:
            if set(r) != {"criterion_id", "outcome", "reason_codes", "evidence_ids"}:
                bad.append("result keys")
                continue
            if r["outcome"] not in self.REASONS:
                bad.append("outcome vocabulary")
                continue
            rc, ev = r["reason_codes"], r["evidence_ids"]
            if not (isinstance(rc, list) and 1 <= len(rc) <= 2 and len(set(rc)) == len(rc) and set(rc) <= self.REASONS[r["outcome"]]):
                bad.append("reason codes")
            if not (isinstance(ev, list) and len(set(ev)) == len(ev) and set(ev) <= self.VALID_IDS and ev == sorted(ev)):
                bad.append("evidence ids %r" % (ev,))
            if r["outcome"] == "MET" and isinstance(ev, list) and not (set(ev) - self.EXTERNAL_IDS):
                bad.append("MET without non-external evidence")
        outs = [r["outcome"] for r in rs]
        derived = "PARTIALLY_FULFILLED" if ("NOT_MET" in outs and "MET" in outs) else "NOT_FULFILLED" if "NOT_MET" in outs else "INDETERMINATE" if "INDETERMINATE" in outs else "FULFILLED"
        if p["overall_outcome"] != derived:
            bad.append("overall inconsistent")
        return bad

    def mutate(self, rnd, p):
        POOL = [None, True, False, 0, 1, 2, -1, "", "MET", "NOT_MET", "INDETERMINATE", "FULFILLED", "NOT_FULFILLED", "PARTIALLY_FULFILLED",
                "INDETERMINATE", "C1", "C2", "C3", "C9", "S:#DELIVERY", "S:E1", "S:E2", "C:X1", "ghost", "EVIDENCE_SUFFICIENT",
                "DELIVERY_INCOMPLETE", "REQUIREMENT_NOT_ADDRESSED", "EVIDENCE_INSUFFICIENT", "UNVERIFIABLE_CLAIM", [], ["MET"], {}, "ab" * 32]
        p = copy.deepcopy(p)
        for _ in range(rnd.choice([1, 1, 1, 2])):
            nodes = []

            def walk(node, parent, key):
                nodes.append((node, parent, key))
                if isinstance(node, dict):
                    for k in list(node):
                        walk(node[k], node, k)
                elif isinstance(node, list):
                    for i in range(len(node)):
                        walk(node[i], node, i)

            walk(p, None, None)
            node, parent, key = rnd.choice(nodes)
            action = rnd.choice(["delete", "replace", "replace", "replace", "dup", "swap", "extra", "reverse"])
            if action == "replace" and parent is not None:
                parent[key] = rnd.choice(POOL)
            elif action == "delete" and parent is not None:
                if isinstance(parent, dict):
                    del parent[key]
                else:
                    parent.pop(key)
            elif action == "dup" and isinstance(node, list) and node:
                node.append(copy.deepcopy(rnd.choice(node)))
            elif action == "swap" and isinstance(node, list) and len(node) > 1:
                a, b = rnd.sample(range(len(node)), 2)
                node[a], node[b] = node[b], node[a]
            elif action == "extra" and isinstance(node, dict):
                node[rnd.choice(["extra", "explanation", "score"])] = rnd.choice(POOL)
            elif action == "reverse" and isinstance(node, list):
                node.reverse()
            elif action == "replace" and parent is None:
                p = rnd.choice(POOL)
        return p

    def test_mutation_fuzz(self):
        rnd = random.Random(20261124)
        honest_material = self.material(self.honest)
        install_llm({"C1": "MET", "C2": "NOT_MET", "C3": "INDETERMINATE"})
        self.assertTrue(self.validator_fn(gl.vm.Return(copy.deepcopy(self.honest))), "honest proposal must pass")
        n = accepted_same = accepted_immaterial = 0
        material_accepted = []
        structural_accepted = []
        immaterial_examples = []
        immaterial_kinds = {}
        for _ in range(20000):
            m = self.mutate(rnd, self.honest)
            if m == self.honest:
                continue
            n += 1
            if self.validator_fn(gl.vm.Return(copy.deepcopy(m))):
                if self.material(m) != honest_material:
                    material_accepted.append(m)
                elif self.structural_violations(m):
                    structural_accepted.append((self.structural_violations(m), m))
                else:
                    accepted_immaterial += 1
                    kinds = set()
                    for a, b in zip(self.honest["criteria_results"], m["criteria_results"]):
                        if a["reason_codes"] != b["reason_codes"]:
                            kinds.add("reason_codes")
                        if a["evidence_ids"] != b["evidence_ids"]:
                            kinds.add("evidence_ids")
                    immaterial_kinds["+".join(sorted(kinds)) or "other"] = immaterial_kinds.get("+".join(sorted(kinds)) or "other", 0) + 1
                    if len(immaterial_examples) < 5:
                        immaterial_examples.append(m["criteria_results"])
        STATS["A3_mutations_tested"] = n
        STATS["A3_accepted_material_changes"] = len(material_accepted)
        STATS["A3_accepted_immaterial_changes"] = accepted_immaterial
        STATS["A3_immaterial_examples"] = immaterial_examples
        STATS["A3_immaterial_by_changed_field"] = immaterial_kinds
        self.assertEqual(set(immaterial_kinds) - {"reason_codes", "evidence_ids", "evidence_ids+reason_codes"}, set(), "accepted change outside reason_codes/evidence_ids")
        self.assertEqual(self.honest, self.honest_snapshot, "validator mutated the leader value in place")
        STATS["A3_accepted_with_structural_violation"] = len(structural_accepted)
        self.assertEqual(structural_accepted, [], "a structurally invalid proposal was accepted: %r" % structural_accepted[:2])
        self.assertEqual(material_accepted, [], "a materially different proposal was accepted: %r" % material_accepted[:2])

    def test_validator_rejects_whenever_its_own_outcome_differs(self):
        rnd = random.Random(7)
        base = {"C1": "MET", "C2": "NOT_MET", "C3": "INDETERMINATE"}
        tested = 0
        for _ in range(300):
            own = {k: rnd.choice(["MET", "NOT_MET", "INDETERMINATE"]) for k in base}
            install_llm(own)
            ok = self.validator_fn(gl.vm.Return(copy.deepcopy(self.honest)))
            tested += 1
            self.assertEqual(ok, own == base, "own=%r" % own)
        STATS["A3_own_outcome_cases"] = tested

    def test_verifier_veto_on_any_single_criterion(self):
        for target in ("C1", "C2", "C3"):
            install_llm({"C1": "MET", "C2": "NOT_MET", "C3": "INDETERMINATE"}, verify={k: ("UNSUPPORTED" if k == target else "SUPPORTED") for k in ("C1", "C2", "C3")})
            self.assertFalse(self.validator_fn(gl.vm.Return(copy.deepcopy(self.honest))), target)

    def test_stored_result_equals_accepted_proposal(self):
        env = Env()
        cid = env.challenged("persist")
        install_llm({"C1": "MET", "C2": "NOT_MET", "C3": "INDETERMINATE"})
        aid = env.adjudicate(cid)
        leader_fn, _ = gl.vm.state.last
        proposal = leader_fn()
        adj = env.c.get_adjudication(aid)
        self.assertEqual(adj["criteria_results"], proposal["criteria_results"])
        self.assertEqual(adj["overall_outcome"], proposal["overall_outcome"])
        for k in ("commitment_id", "submission_id", "challenge_id", "evidence_package_hash"):
            self.assertEqual(adj[k], proposal[k])
        self.assertEqual(adj["result_hash"], ar._result_hash(cid, adj["submission_id"], adj["challenge_id"], adj["evidence_package_hash"], adj["overall_outcome"], adj["criteria_results"]))


# =============================================================================================
class A4_EvidenceIntegrity(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        install_llm({"C1": "MET", "C2": "NOT_MET", "C3": "INDETERMINATE"})

    def test_byte_exactness_variants_all_rejected(self):
        content = "Caf\u00e9 report\nline two \u2014 risks: delay, cost, scope. "
        cid = self.env.challenged("u1", content=content)
        variants = {
            "NFD instead of NFC": unicodedata.normalize("NFD", content),
            "CRLF instead of LF": content.replace("\n", "\r\n"),
            "trailing space removed": content.rstrip(),
            "leading BOM": "\ufeff" + content,
            "zero-width space inserted": content.replace("report", "re\u200bport"),
            "homoglyph (Cyrillic a)": content.replace("a", "\u0430", 1),
            "truncated": content[:-3],
            "tab instead of space": content.replace(" ", "\t", 1),
            "case change": content.upper(),
        }
        rejected = {}
        for name, v in variants.items():
            self.assertNotEqual(v, content, name)
            try:
                self.env.adjudicate(cid, content=v)
                rejected[name] = "ACCEPTED (BUG)"
            except gl.vm.UserError as exc:
                rejected[name] = str(exc.data).split(":")[0]
        STATS["A4_variants"] = rejected
        self.assertTrue(all(r.endswith("HASH_MISMATCH") for r in rejected.values()), rejected)
        self.assertEqual(self.env.status(cid), "CHALLENGED")
        self.env.adjudicate(cid, content=content)  # the exact original still works
        self.assertEqual(self.env.status(cid), "ADJUDICATED")

    def test_evidence_manifest_variants_rejected(self):
        cid = self.env.challenged("m1")
        bad = [
            EVID[:1], EVID + [{"id": "E3", "kind": "TEXT", "content": "extra"}],
            [dict(EVID[0], id="E9"), EVID[1]], [dict(EVID[0], kind="STRUCTURED"), EVID[1]],
            [dict(EVID[0], content=EVID[0]["content"] + " "), EVID[1]], [EVID[1], dict(EVID[0], content="Draft word count is 121")],
        ]
        for e in bad:
            with self.assertRaises(gl.vm.UserError) as cm:
                self.env.adjudicate(cid, evid=e)
            self.assertIn("HASH_MISMATCH", str(cm.exception.data))

    def test_cross_record_substitution(self):
        env = self.env
        a = env.challenged("A", content="Material of A", evid=[{"id": "E1", "kind": "TEXT", "content": "evidence A"}], statement="stmt A", ch_evid=[])
        b = env.challenged("B", content="Material of B", evid=[{"id": "E1", "kind": "TEXT", "content": "evidence B"}], statement="stmt B", ch_evid=[])
        with self.assertRaises(gl.vm.UserError):
            env.adjudicate(a, content="Material of B", evid=[{"id": "E1", "kind": "TEXT", "content": "evidence B"}], statement="stmt B", ch_evid=[])
        with self.assertRaises(gl.vm.UserError):
            env.adjudicate(b, content="Material of A", evid=[{"id": "E1", "kind": "TEXT", "content": "evidence A"}], statement="stmt A", ch_evid=[])
        # bytes mix: A's content with B's evidence
        with self.assertRaises(gl.vm.UserError):
            env.adjudicate(a, content="Material of A", evid=[{"id": "E1", "kind": "TEXT", "content": "evidence B"}], statement="stmt A", ch_evid=[])
        self.assertEqual((env.status(a), env.status(b)), ("CHALLENGED", "CHALLENGED"))

    def test_identical_bytes_in_two_commitments_stay_isolated(self):
        env = self.env
        a = env.challenged("same1")
        b = env.challenged("same2")
        aid = env.adjudicate(a)
        self.assertEqual(env.status(b), "CHALLENGED")
        bid = env.adjudicate(b)
        ra, rb = env.c.get_adjudication(aid), env.c.get_adjudication(bid)
        self.assertNotEqual(aid, bid)
        self.assertNotEqual(ra["evidence_package_hash"], rb["evidence_package_hash"])
        self.assertNotEqual(env.c.get_commitment(a)["commitment_hash"], env.c.get_commitment(b)["commitment_hash"])
        self.assertEqual((ra["commitment_id"], rb["commitment_id"]), (a, b))

    def test_json_edge_cases(self):
        cid = self.env.accepted("j1")
        self.env.as_(EXE)
        before = snapshot(self.env.c)
        cases = {
            "lone surrogate escape in JSON string": '[{"id":"E1","kind":"TEXT","content":"bad \\ud800 surrogate"}]',
            "NaN constant": '[NaN]',
            "huge integer": "[" + "1" * 5000 + "]",
            "object not list": '{"id":"E1"}',
            "null": "null",
            "trailing garbage": '[] x',
            "non-string id": '[{"id":1,"kind":"TEXT","content":"x"}]',
            "id with colon": '[{"id":"S:evil","kind":"TEXT","content":"x"}]',
            "id with hash": '[{"id":"#DELIVERY","kind":"TEXT","content":"x"}]',
            "kind as list": '[{"id":"E1","kind":["TEXT"],"content":"x"}]',
            "content as object": '[{"id":"E1","kind":"TEXT","content":{"a":1}}]',
            "nul inside JSON string": '[{"id":"E1","kind":"TEXT","content":"a\\u0000b"}]',
        }
        out = {}
        for name, text in cases.items():
            try:
                self.env.c.submit_delivery(cid, CONTENT, text)
                out[name] = "ACCEPTED (BUG)"
            except gl.vm.UserError as exc:
                out[name] = str(exc.data)
        STATS["A4_json_edge_cases"] = out
        self.assertFalse([k for k, v in out.items() if v.startswith("ACCEPTED")], out)
        self.assertEqual(before, snapshot(self.env.c))

    def test_duplicate_json_keys_last_wins_is_deterministic(self):
        """FINDING input: duplicate object keys are not rejected. Last key wins (CPython json); the hash
        covers the parsed value, so evaluated == committed, but a client may be surprised."""
        cid = self.env.accepted("dk")
        self.env.as_(EXE)
        text = '[{"id":"E1","id":"E2","kind":"TEXT","content":"x"}]'
        sid = self.env.c.submit_delivery(cid, CONTENT, text)
        STATS["A4_duplicate_json_keys_accepted"] = True
        self.assertEqual(self.env.c.get_submission(sid)["evidence_count"], 1)

    def test_reserved_delivery_id_cannot_be_forged(self):
        pkg = ar._build_package("d", [{"id": "E1", "kind": "TEXT", "content": "a"}], [{"id": "E1", "kind": "TEXT", "content": "b"}])
        self.assertEqual([p["id"] for p in pkg], ["S:#DELIVERY", "S:E1", "C:E1"])


# =============================================================================================
class A5_AuthorizationAndRelayer(unittest.TestCase):
    def test_actor_by_operation_matrix(self):
        actors = {"requester": REQ, "executor": EXE, "other": OTH}
        ops = {
            "accept": ("executor", lambda e: e.create(), lambda e, c: e.c.accept_commitment(c)),
            "reject": ("executor", lambda e: e.create(), lambda e, c: e.c.reject_commitment(c)),
            "cancel": ("requester", lambda e: e.create(), lambda e, c: e.c.cancel_commitment(c)),
            "submit": ("executor", lambda e: e.accepted(), lambda e, c: e.c.submit_delivery(c, CONTENT, j(EVID))),
            "challenge": ("requester", lambda e: e.submitted(), lambda e, c: e.c.create_challenge(c, STATEMENT, j(DISPUTED), j(CH_EVID))),
            "close": ("requester", lambda e: e.submitted(), lambda e, c: e.c.close_uncontested(c)),
            "adjudicate": (None, lambda e: e.challenged(), lambda e, c: e.c.adjudicate(c, CONTENT, j(EVID), STATEMENT, j(DISPUTED), j(CH_EVID))),
        }
        table = {}
        for op, (allowed, prep, call) in ops.items():
            for aname, actor in actors.items():
                env = Env()
                install_llm({"C1": "MET", "C2": "MET", "C3": "MET"})
                cid = prep(env)
                env.as_(actor)
                try:
                    call(env, cid)
                    result = "allowed"
                except gl.vm.UserError as exc:
                    result = "denied:" + str(exc.data).split(":")[0].replace("[EXPECTED] ", "")
                table["%s/%s" % (op, aname)] = result
                expect_allowed = allowed is None or allowed == aname
                self.assertEqual(result == "allowed", expect_allowed, "%s by %s -> %s" % (op, aname, result))
                if not expect_allowed:
                    self.assertEqual(result, "denied:UNAUTHORIZED")
        STATS["A5_matrix"] = table

    def test_relayer_has_no_authority_over_inputs_or_verdict(self):
        env = Env()
        cid = env.challenged("rel")
        install_llm({"C1": "MET", "C2": "NOT_MET", "C3": "MET"})
        for who in (OTH, REQ2):
            for kwargs in (dict(content="other"), dict(statement="other"), dict(disputed=["C2"]), dict(evid=[]), dict(ch_evid=[])):
                with self.assertRaises(gl.vm.UserError):
                    env.adjudicate(cid, who=who, **kwargs)
        self.assertEqual(env.status(cid), "CHALLENGED")
        aid = env.adjudicate(cid, who=OTH)
        adj = env.c.get_adjudication(aid)
        com = env.c.get_commitment(cid)
        self.assertEqual((com["requester"], com["executor"]), (REQ.as_hex, EXE.as_hex))
        self.assertEqual(adj["relayed_by"], OTH.as_hex)
        with self.assertRaises(gl.vm.UserError):
            env.adjudicate(cid, who=REQ2)  # a second relayer cannot overwrite
        self.assertEqual(env.c.get_adjudication(aid), adj)

    def test_no_adjudicate_without_challenge_in_any_state(self):
        env = Env()
        install_llm({"C1": "MET", "C2": "MET", "C3": "MET"})
        for builder in (env.create, env.accepted, env.submitted):
            cid = builder("x%d" % len(env.c.commitments))
            with self.assertRaises(gl.vm.UserError) as cm:
                env.adjudicate(cid)
            self.assertIn("INVALID_STATE", str(cm.exception.data))
        self.assertEqual(gl.vm.state.llm_calls, 0)

    def test_uncontested_cannot_be_challenged_or_adjudicated(self):
        env = Env()
        cid = env.submitted("unc")
        env.as_(REQ)
        env.c.close_uncontested(cid)
        install_llm({"C1": "MET", "C2": "MET", "C3": "MET"})
        with self.assertRaises(gl.vm.UserError):
            env.c.create_challenge(cid, STATEMENT, j(DISPUTED), "[]")
        with self.assertRaises(gl.vm.UserError):
            env.adjudicate(cid)
        self.assertEqual(env.c.get_commitment(cid)["adjudication_id"], "")


# =============================================================================================
class A6_RecordIdentifiersAndReplay(unittest.TestCase):
    def test_many_commitments_same_wallets_exact_lookup(self):
        env = Env()
        install_llm({"C1": "MET", "C2": "NOT_MET", "C3": "INDETERMINATE"})
        ids = [env.challenged("n%d" % i, content="content %d" % i, evid=[{"id": "E1", "kind": "TEXT", "content": "ev %d" % i}], statement="stmt %d" % i, ch_evid=[]) for i in range(8)]
        self.assertEqual(len(set(ids)), 8)
        adjs = {}
        for i in (5, 2, 7, 0):
            adjs[i] = env.adjudicate(ids[i], content="content %d" % i, evid=[{"id": "E1", "kind": "TEXT", "content": "ev %d" % i}], statement="stmt %d" % i, ch_evid=[])
        for i in range(8):
            v = env.c.get_commitment(ids[i])
            sub = env.c.get_submission(v["submission_id"])
            ch = env.c.get_challenge(v["challenge_id"])
            self.assertEqual((sub["commitment_id"], ch["commitment_id"], ch["submission_id"]), (ids[i], ids[i], sub["submission_id"]))
            self.assertEqual(ch["statement"], "stmt %d" % i)
            if i in adjs:
                a = env.c.get_adjudication(v["adjudication_id"])
                self.assertEqual((v["status"], a["commitment_id"], a["adjudication_id"]), ("ADJUDICATED", ids[i], adjs[i]))
            else:
                self.assertEqual((v["status"], v["adjudication_id"]), ("CHALLENGED", ""))

    def test_same_nonce_different_requesters_and_executors(self):
        env = Env()
        a = env.create("same", REQ, EXE)
        b = env.create("same", REQ2, EXE)
        c = env.create("same2", REQ, OTH)
        self.assertEqual(len({a, b, c}), 3)
        self.assertEqual(env.c.get_commitment(b)["requester"], REQ2.as_hex)
        self.assertEqual(env.c.get_commitment(c)["executor"], OTH.as_hex)
        self.assertEqual(env.c.compute_commitment_id(REQ.as_hex, "same"), a)

    def test_every_successful_write_is_not_replayable(self):
        env = Env()
        install_llm({"C1": "MET", "C2": "MET", "C3": "MET"})
        cid = env.create("rp")
        env.as_(EXE)
        env.c.accept_commitment(cid)
        replay = {
            "create": lambda: (env.as_(REQ), env.c.create_commitment("rp", EXE.as_hex, "Deliver a risk report", j(CRITERIA3), j(KINDS))),
            "accept": lambda: (env.as_(EXE), env.c.accept_commitment(cid)),
            "reject": lambda: (env.as_(EXE), env.c.reject_commitment(cid)),
            "cancel": lambda: (env.as_(REQ), env.c.cancel_commitment(cid)),
        }
        for name, fn in replay.items():
            before = snapshot(env.c)
            with self.assertRaises(gl.vm.UserError, msg=name):
                fn()
            self.assertEqual(before, snapshot(env.c))
        env.as_(EXE)
        env.c.submit_delivery(cid, CONTENT, j(EVID))
        for fn in (lambda: env.c.submit_delivery(cid, CONTENT, j(EVID)), lambda: env.c.accept_commitment(cid)):
            env.as_(EXE)
            with self.assertRaises(gl.vm.UserError):
                fn()
        env.as_(REQ)
        env.c.create_challenge(cid, STATEMENT, j(DISPUTED), j(CH_EVID))
        for fn in (lambda: env.c.create_challenge(cid, STATEMENT, j(DISPUTED), j(CH_EVID)), lambda: env.c.close_uncontested(cid)):
            with self.assertRaises(gl.vm.UserError):
                fn()
        aid = env.adjudicate(cid)
        snap = snapshot(env.c)
        for who in (REQ, EXE, OTH):
            with self.assertRaises(gl.vm.UserError):
                env.adjudicate(cid, who=who)
        self.assertEqual(snap, snapshot(env.c))
        self.assertEqual(env.c.get_adjudication(aid)["adjudication_id"], aid)

    def test_terminal_states_are_closed(self):
        env = Env()
        install_llm({"C1": "MET", "C2": "MET", "C3": "MET"})
        terminals = {}
        terminals["REJECTED"] = env.create("t1")
        env.as_(EXE)
        env.c.reject_commitment(terminals["REJECTED"])
        terminals["CANCELLED"] = env.create("t2")
        env.as_(REQ)
        env.c.cancel_commitment(terminals["CANCELLED"])
        terminals["UNCONTESTED"] = env.submitted("t3")
        env.as_(REQ)
        env.c.close_uncontested(terminals["UNCONTESTED"])
        terminals["ADJUDICATED"] = env.challenged("t4")
        env.adjudicate(terminals["ADJUDICATED"])
        ops = [
            (EXE, lambda c: env.c.accept_commitment(c)), (EXE, lambda c: env.c.reject_commitment(c)), (REQ, lambda c: env.c.cancel_commitment(c)),
            (EXE, lambda c: env.c.submit_delivery(c, CONTENT, j(EVID))), (REQ, lambda c: env.c.create_challenge(c, STATEMENT, j(DISPUTED), "[]")),
            (REQ, lambda c: env.c.close_uncontested(c)), (OTH, lambda c: env.adjudicate(c)),
        ]
        for state, cid in terminals.items():
            for who, fn in ops:
                before = snapshot(env.c)
                env.as_(who)
                with self.assertRaises(gl.vm.UserError, msg=state):
                    fn(cid)
                self.assertEqual(before, snapshot(env.c))
                self.assertEqual(env.status(cid), state)

    def test_no_exit_from_challenged_except_adjudicate(self):
        """Documents FINDING (permanent CHALLENGED if adjudication can never complete)."""
        env = Env()
        cid = env.challenged("stuck")
        gl.nondet.responder = lambda p: (_ for _ in ()).throw(RuntimeError("provider unavailable"))
        exits = {}
        for name, who, fn in [("accept", EXE, lambda: env.c.accept_commitment(cid)), ("reject", EXE, lambda: env.c.reject_commitment(cid)),
                              ("cancel", REQ, lambda: env.c.cancel_commitment(cid)), ("close_uncontested", REQ, lambda: env.c.close_uncontested(cid)),
                              ("submit", EXE, lambda: env.c.submit_delivery(cid, CONTENT, "[]")),
                              ("challenge_again", REQ, lambda: env.c.create_challenge(cid, STATEMENT, j(DISPUTED), "[]")),
                              ("adjudicate", OTH, lambda: env.adjudicate(cid))]:
            env.as_(who)
            try:
                fn()
                exits[name] = "SUCCEEDED"
            except gl.vm.UserError as exc:
                exits[name] = str(exc.data).split(":")[0]
            except gl.ConsensusDisagreement:
                exits[name] = "CONSENSUS_FAILURE"
        STATS["A6_exits_from_CHALLENGED_when_llm_unavailable"] = exits
        self.assertEqual(env.status(cid), "CHALLENGED")
        self.assertNotIn("SUCCEEDED", exits.values())


# =============================================================================================
class A7_ConsensusStructure(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        cid = self.env.challenged()
        install_llm({"C1": "MET", "C2": "MET", "C3": "MET"})
        self.env.adjudicate(cid)
        self.leader_fn, self.validator_fn = gl.vm.state.last

    def test_closures_capture_only_plain_data(self):
        for fn in (self.leader_fn, self.validator_fn):
            self.assertEqual(fn.__code__.co_freevars, ("ctx",), fn.__name__)
        ctx = self.leader_fn.__closure__[0].cell_contents
        json.dumps(ctx)  # plain JSON-able data only
        STATS["A7_closure_freevars"] = {"leader_fn": list(self.leader_fn.__code__.co_freevars), "validator_fn": list(self.validator_fn.__code__.co_freevars)}

    def test_cloudpickle_roundtrip_of_closures(self):
        try:
            import cloudpickle
        except ImportError:
            self.skipTest("cloudpickle not installed")
        for fn in (self.leader_fn, self.validator_fn):
            blob = cloudpickle.dumps(fn)
            clone = pickle.loads(blob)
            self.assertTrue(callable(clone))
        clone_leader = pickle.loads(cloudpickle.dumps(self.leader_fn))
        install_llm({"C1": "MET", "C2": "MET", "C3": "MET"})
        self.assertEqual(clone_leader()["overall_outcome"], "FULFILLED")
        clone_validator = pickle.loads(cloudpickle.dumps(self.validator_fn))
        self.assertTrue(clone_validator(gl.vm.Return(clone_leader())))
        STATS["A7_cloudpickle_roundtrip"] = "leader_fn and validator_fn pickled/unpickled and executed (cloudpickle %s)" % cloudpickle.__version__

    def test_no_storage_access_or_writes_inside_or_before_nondet_block(self):
        tree = ast.parse(SOURCE)
        cls = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AgentRecall"][0]
        fn = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "adjudicate"][0]
        nondet_line = None
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and ast.unparse(node.func).endswith("run_nondet_default"):
                nondet_line = node.lineno
        self.assertIsNotNone(nondet_line)
        nested = [n for n in ast.walk(fn) if isinstance(n, ast.FunctionDef) and n.name in ("leader_fn", "validator_fn")]
        self.assertEqual(len(nested), 2)
        for n in nested:
            for sub in ast.walk(n):
                if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == "self":
                    self.fail("nested nondet function touches self at line %d" % sub.lineno)
        writes = []
        for node in ast.walk(fn):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            for t in targets:
                src = ast.unparse(t)
                if src.startswith("self."):
                    writes.append((node.lineno, src))
        STATS["A7_storage_writes_in_adjudicate"] = writes
        self.assertTrue(writes)
        for line, src in writes:
            self.assertGreater(line, nondet_line, "storage write before the non-deterministic block: %s" % src)

    def test_deterministic_code_has_no_set_or_dict_iteration_order_dependence(self):
        """Lists every `for` loop in the module so a human can review iteration sources; automatically
        fails only if a loop iterates directly over a set literal / set() call."""
        tree = ast.parse(SOURCE)
        loops = []
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                it = node.iter
                src = ast.unparse(it)
                loops.append((node.lineno, src))
                if isinstance(it, ast.Set) or (isinstance(it, ast.Call) and ast.unparse(it.func) in ("set", "frozenset")):
                    self.fail("iteration over a set at line %d" % node.lineno)
        STATS["A7_for_loops_reviewed"] = len(loops)
        STATS["A7_for_loop_iterables"] = sorted(set(s for _, s in loops))

    def test_error_messages_are_deterministic_strings(self):
        for m in re.findall(r'_fail\(([^)]*)\)', SOURCE):
            self.assertNotRegex(m, r"%|\.format|f\"|time|random")

    def test_weak_validator_counterfactual_is_rejected_by_the_real_one(self):
        env = Env()
        cid = env.challenged("cf")
        install_llm({"C1": "MET", "C2": "NOT_MET", "C3": "INDETERMINATE"})
        env.adjudicate(cid)
        leader_fn, validator_fn = gl.vm.state.last
        honest = leader_fn()
        forged = copy.deepcopy(honest)
        forged["criteria_results"][0]["evidence_ids"] = ["S:ghost"]
        forged["criteria_results"][1]["reason_codes"] = ["EVIDENCE_CONTRADICTS"]

        def weak(res):  # only checks the overall verdict, the failure mode the audit warns about
            return res.calldata["overall_outcome"] == honest["overall_outcome"]

        self.assertTrue(weak(gl.vm.Return(forged)))
        self.assertFalse(validator_fn(gl.vm.Return(forged)))


# =============================================================================================
class A8_PromptAndResourceBounds(unittest.TestCase):
    def capture(self, content, ev_content, st, ch_content, criteria_text, desc):
        env = Env(criteria=[{"id": "C%d" % i, "text": criteria_text} for i in range(10)])
        prompts = []

        def responder(prompt):
            prompts.append(prompt)
            ids = ["C%d" % i for i in range(10)]
            if "ROLE: EVALUATOR" in prompt:
                return {"criteria_results": [res(c, "MET", cited=["S:#DELIVERY"]) for c in ids]}
            return {"verdicts": [{"criterion_id": c, "verdict": "SUPPORTED"} for c in ids]}

        gl.nondet.responder = responder
        t = {}
        env.as_(REQ)
        s0 = time.perf_counter()
        cid = env.c.create_commitment("big", EXE.as_hex, desc, j(env.criteria), j(KINDS))
        t["create_commitment"] = time.perf_counter() - s0
        env.as_(EXE)
        env.c.accept_commitment(cid)
        ev = [{"id": "E%02d" % i, "kind": "TEXT", "content": ("%02d" % i) + ev_content} for i in range(12)]
        s0 = time.perf_counter()
        env.c.submit_delivery(cid, content, j(ev))
        t["submit_delivery"] = time.perf_counter() - s0
        env.as_(REQ)
        ch_ev = [{"id": "X%d" % i, "kind": "TEXT", "content": ("%d" % i) + ch_content} for i in range(6)]
        s0 = time.perf_counter()
        env.c.create_challenge(cid, st, j(["C0"]), j(ch_ev))
        t["create_challenge"] = time.perf_counter() - s0
        env.as_(OTH)
        s0 = time.perf_counter()
        env.c.adjudicate(cid, content, j(ev), st, j(["C0"]), j(ch_ev))
        t["adjudicate_incl_mock_llm_and_stub_validator"] = time.perf_counter() - s0
        sizes = {"eval_prompt_bytes": max(len(p.encode()) for p in prompts if "ROLE: EVALUATOR" in p),
                 "verify_prompt_bytes": max(len(p.encode()) for p in prompts if "ROLE: VERIFIER" in p)}
        return sizes, t

    def test_maximum_valid_input_prompt_sizes_ascii_vs_astral(self):
        ascii_sizes, ascii_t = self.capture("A" * 6000, "A" * 1330, "S" * 1500, "A" * 1330, "C" * 400, "D" * 1500)
        astral = "\U0001F600"
        a_sizes, a_t = self.capture(astral * 1500, astral * 330, astral * 375, astral * 330, astral * 100, astral * 375)
        STATS["A8_max_ascii"] = {"prompt": ascii_sizes, "seconds": {k: round(v, 4) for k, v in ascii_t.items()}}
        STATS["A8_max_astral"] = {"prompt": a_sizes, "seconds": {k: round(v, 4) for k, v in a_t.items()}}
        STATS["A8_astral_inflation_factor_eval"] = round(a_sizes["eval_prompt_bytes"] / ascii_sizes["eval_prompt_bytes"], 2)

    def test_oversized_inputs_are_rejected_fast_and_without_llm(self):
        env = Env()
        install_llm({"C1": "MET", "C2": "MET", "C3": "MET"})
        cid = env.challenged("os")
        big = "A" * 300_000
        timings = {}
        probes = {
            "adjudicate content": lambda: env.adjudicate(cid, content=big),
            "adjudicate evidence_json": lambda: env.c.adjudicate(cid, CONTENT, big, STATEMENT, j(DISPUTED), "[]"),
            "adjudicate challenge_statement": lambda: env.adjudicate(cid, statement=big),
            "adjudicate disputed_json": lambda: env.c.adjudicate(cid, CONTENT, j(EVID), STATEMENT, big, "[]"),
            "adjudicate challenge_evidence_json": lambda: env.c.adjudicate(cid, CONTENT, j(EVID), STATEMENT, j(DISPUTED), big),
            "create_commitment description": lambda: env.c.create_commitment("o1", EXE.as_hex, big, j(CRITERIA3), j(KINDS)),
            "create_commitment criteria_json": lambda: env.c.create_commitment("o2", EXE.as_hex, "d", big, j(KINDS)),
            "create_commitment nonce": lambda: env.c.create_commitment(big, EXE.as_hex, "d", j(CRITERIA3), j(KINDS)),
        }
        env.as_(REQ)
        for name, fn in probes.items():
            env.as_(OTH if name.startswith("adjudicate") else REQ)
            s0 = time.perf_counter()
            with self.assertRaises(gl.vm.UserError):
                fn()
            timings[name] = round(time.perf_counter() - s0, 4)
        STATS["A8_300KB_rejection_seconds"] = timings
        self.assertLess(max(timings.values()), 1.0)
        self.assertEqual(gl.vm.state.llm_calls, 0)

    def test_pure_python_keccak_cost_at_maximum_hashed_volume(self):
        saved = ar._SdkKeccak256
        ar._SdkKeccak256 = None
        try:
            s0 = time.perf_counter()
            for n in (6000, 16000, 10000):
                ar._keccak256_pure(b"x" * n)
            STATS["A8_pure_keccak_seconds_for_32KB_cpython"] = round(time.perf_counter() - s0, 4)
        finally:
            ar._SdkKeccak256 = saved


# =============================================================================================
class A9_SdkCompatibilityStatic(unittest.TestCase):
    """Static comparison against the v0.4 migration guide items named in the audit prompt."""

    def line_of(self, pattern):
        for i, line in enumerate(SOURCE.splitlines(), 1):
            if re.search(pattern, line):
                return i
        return None

    def test_checklist(self):
        checks = [
            ("runner header lines 1-2 (# v0.4.0 + Depends py-genlayer:kzybg95x...)", r'^# \{ "Depends": "py-genlayer:kzybg95x1gn21dw72m7hyg0maaap04n4nx55j9yt6fkdqxtz6bz0" \}', True),
            ("import genlayer as gl", r"^import genlayer as gl$", True),
            ("from genlayer.types import *", r"^from genlayer.types import \*$", True),
            ("gl.contract.Contract base class", r"class AgentRecall\(gl\.contract\.Contract\)", True),
            ("@gl.storage.allow on storage dataclasses", r"^@gl\.storage\.allow$", True),
            ("gl.storage.TreeMap annotations", r"gl\.storage\.TreeMap\[", True),
            ("run_nondet_default used", r"gl\.vm\.run_nondet_default\(", True),
            ("UserError with a single string", r'gl\.vm\.UserError\("', True),
            ("generic run_nondet / run_nondet_unsafe NOT used", r"run_nondet_unsafe|gl\.vm\.run_nondet\(", False),
            ("removed __receive__ NOT used", r"__receive__", False),
            ("salt_nonce NOT used", r"salt_nonce", False),
            ("old import style NOT used (from genlayer import *)", r"^from genlayer import \*", False),
            ("old base class NOT used (gl.Contract)", r"\bgl\.Contract\b", False),
            ("old storage decorator NOT used (allow_storage)", r"allow_storage", False),
            ("old message accessor NOT used (gl.message_raw)", r"gl\.message_raw", False),
            ("eq_principle NOT used", r"gl\.eq_principle", False),
            ("web access NOT used", r"gl\.nondet\.web", False),
            ("exec_prompt response_format NOT used", r"response_format", False),
        ]
        table = []
        for name, pat, must_exist in checks:
            ln = self.line_of(pat)
            ok = (ln is not None) == must_exist
            table.append((name, "PASS" if ok else "FAIL", ln))
            self.assertTrue(ok, name)
        STATS["A9_sdk_checklist"] = table
        tree = ast.parse(SOURCE)
        cls = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AgentRecall"][0]
        for fn in cls.body:
            if isinstance(fn, ast.FunctionDef) and fn.name.startswith("__"):
                self.assertEqual(fn.decorator_list, [])



# =============================================================================================
class A10_SpecDiscrepancies(unittest.TestCase):
    def test_all_criteria_are_evaluated_not_only_disputed_ones(self):
        """Binding spec 1.3 step 6: 'Adjudication evaluates the DISPUTED criteria'. Implementation: every committed
        criterion is evaluated (decision E12). Demonstration: challenge only C1; the undisputed C2 comes back
        NOT_MET and changes the overall result."""
        env = Env()
        cid = env.challenged("e12")  # DISPUTED == ["C1"]
        seen = {}

        def responder(prompt):
            if "ROLE: EVALUATOR" in prompt:
                seen["criteria_in_prompt"] = json.loads(prompt.partition("DATA:\n")[2])["criteria"]
                return {"criteria_results": [res("C1", "MET"), res("C2", "NOT_MET"), res("C3", "MET")]}
            return {"verdicts": [{"criterion_id": c, "verdict": "SUPPORTED"} for c in ("C1", "C2", "C3")]}

        gl.nondet.responder = responder
        aid = env.adjudicate(cid)
        adj = env.c.get_adjudication(aid)
        ch = env.c.get_challenge(env.c.get_commitment(cid)["challenge_id"])
        STATS["A10_disputed"] = ch["disputed_criterion_ids"]
        STATS["A10_criteria_sent_to_llm"] = [c["id"] for c in seen["criteria_in_prompt"]]
        STATS["A10_overall"] = adj["overall_outcome"]
        STATS["A10_undisputed_results"] = [(r["criterion_id"], r["outcome"]) for r in adj["criteria_results"] if r["criterion_id"] not in ch["disputed_criterion_ids"]]
        self.assertEqual(ch["disputed_criterion_ids"], ["C1"])
        self.assertEqual(STATS["A10_criteria_sent_to_llm"], ["C1", "C2", "C3"])
        self.assertEqual(adj["overall_outcome"], "PARTIALLY_FULFILLED")  # driven by the UNDISPUTED C2


class A11_DocumentationDiscrepancies(unittest.TestCase):
    def test_documented_prompt_size_vs_measured(self):
        hits = []
        docs = os.path.join(REPO, "docs")
        for name in sorted(os.listdir(docs)):
            with open(os.path.join(docs, name), encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    if re.search(r"37 ?KB", line):
                        hits.append("docs/%s:%d" % (name, i))
        STATS["A11_docs_claiming_37KB"] = hits
        self.assertTrue(hits, "expected to find the documented 37 KB figure")


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=2)
    os.makedirs(EVIDENCE, exist_ok=True)
    with open(os.path.join(EVIDENCE, "stats.json"), "w") as fh:
        json.dump(STATS, fh, indent=2, default=str)
    sys.exit(0 if result.result.wasSuccessful() else 1)
