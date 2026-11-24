"""Studio-mode integration tests for contracts/agent_recall.py (gltest).

STATUS: WRITTEN BUT NOT EXECUTED. No Docker, no GenLayer Studio, no gltest and no network
were available where this file was written. Nothing in docs/ claims real consensus has been
verified. Run against a LOCAL Studio only:

    gltest tests/integration/ -v -s --chain-type localnet

Do NOT point this at Studionet, Bradbury, Asimov or any other public network.

API details taken from the genlayer-test material supplied with the project, to be confirmed
on the first real run:
  * get_contract_factory("AgentRecall"), factory.deploy(...), contract.<view>(args=[...]).call()
  * multi-account writes follow the single documented example
    `contract.some_method(args=[...], account=accounts[1])` returning a receipt. If your
    gltest version returns a transaction object instead, adapt `send()` below.
  * tx_execution_succeeded / tx_execution_failed from gltest.assertions
  * ACCEPTED / FINALIZED are lifecycle states, not proof of successful execution; every test
    asserts the execution result AND re-reads contract state.

TOOLING / FEES (Studio v0.123, live since 23 Nov 2026): use genlayer-test 0.30.0 (and genlayer CLI
0.40.0 for a local Studio); every deploy and write needs fees, and a missing fee fails with
FeesDistributionMissing - that is a *fee* error, not a contract error. Check both the transaction
status and the execution result after each call. Whether genlayer-test 0.30.0 attaches the fees for you
is NOT verified here; if writes fail with FeesDistributionMissing, estimate and pass fees explicitly.

These tests use real validators and real LLMs, so verdicts on clear-cut material are expected
but not guaranteed; a transient consensus failure shows up as a failed receipt, never as a
persisted verdict (that property is asserted in test_failed_adjudication_leaves_state_unchanged).
"""

import json

import pytest
from gltest import get_contract_factory
from gltest.assertions import tx_execution_failed, tx_execution_succeeded

CRITERIA = [
    {"id": "C1", "text": "The delivery states that the project name is Atlas"},
    {"id": "C2", "text": "The delivery states that the report was prepared in 2026"},
]
KINDS = ["TEXT", "EXTERNAL_REFERENCE"]
CONTENT = "Project name: Atlas. This report was prepared in 2026 by the executor team."
EVID = [{"id": "E1", "kind": "TEXT", "content": "Cover page reads: Atlas, 2026 annual report."}]
STATEMENT = "The requester claims the project name is not stated in the delivery."
CH_EVID = [{"id": "X1", "kind": "TEXT", "content": "Requester could not find the project name."}]


def j(value):
    return json.dumps(value)


def send(contract, method, args, account):
    return getattr(contract, method)(args=args, account=account)


@pytest.fixture(scope="module")
def deployed(accounts):
    factory = get_contract_factory("AgentRecall")
    contract = factory.deploy(args=[])  # constructor takes no arguments
    return contract


def lifecycle_to_challenged(contract, accounts, nonce):
    req, exe = accounts[0], accounts[1]
    cid = contract.compute_commitment_id(args=[req.address, nonce]).call()
    assert tx_execution_succeeded(send(contract, "create_commitment", [nonce, exe.address, "Deliver the Atlas report", j(CRITERIA), j(KINDS)], req))
    assert tx_execution_succeeded(send(contract, "accept_commitment", [cid], exe))
    assert tx_execution_succeeded(send(contract, "submit_delivery", [cid, CONTENT, j(EVID)], exe))
    assert tx_execution_succeeded(send(contract, "create_challenge", [cid, STATEMENT, j(["C1"]), j(CH_EVID)], req))
    return cid


def test_full_lifecycle_with_real_consensus(deployed, accounts):
    cid = lifecycle_to_challenged(deployed, accounts, "it-full")
    assert deployed.get_commitment(args=[cid]).call()["status"] == "CHALLENGED"

    receipt = send(deployed, "adjudicate", [cid, CONTENT, j(EVID), STATEMENT, j(["C1"]), j(CH_EVID)], accounts[2])
    assert tx_execution_succeeded(receipt)

    commitment = deployed.get_commitment(args=[cid]).call()
    assert commitment["status"] == "ADJUDICATED"
    adj = deployed.get_adjudication(args=[commitment["adjudication_id"]]).call()
    assert adj["overall_outcome"] in ("FULFILLED", "PARTIALLY_FULFILLED", "NOT_FULFILLED", "INDETERMINATE")
    assert [r["criterion_id"] for r in adj["criteria_results"]] == ["C1", "C2"]
    for r in adj["criteria_results"]:
        assert r["outcome"] in ("MET", "NOT_MET", "INDETERMINATE")
        assert 1 <= len(r["reason_codes"]) <= 2
    assert adj["commitment_hash"] == commitment["commitment_hash"]
    assert adj["relayed_by"].lower() == accounts[2].address.lower()  # permissionless relay


def test_unauthorized_actions_fail_and_do_not_change_state(deployed, accounts):
    req, exe, other = accounts[0], accounts[1], accounts[2]
    nonce = "it-auth"
    cid = deployed.compute_commitment_id(args=[req.address, nonce]).call()
    assert tx_execution_succeeded(send(deployed, "create_commitment", [nonce, exe.address, "d", j(CRITERIA), j(KINDS)], req))
    assert tx_execution_failed(send(deployed, "accept_commitment", [cid], other))
    assert tx_execution_failed(send(deployed, "cancel_commitment", [cid], exe))
    assert deployed.get_commitment(args=[cid]).call()["status"] == "OPEN"


def test_uncontested_path_is_not_a_verdict(deployed, accounts):
    req, exe = accounts[0], accounts[1]
    nonce = "it-uncontested"
    cid = deployed.compute_commitment_id(args=[req.address, nonce]).call()
    assert tx_execution_succeeded(send(deployed, "create_commitment", [nonce, exe.address, "d", j(CRITERIA), j(KINDS)], req))
    assert tx_execution_succeeded(send(deployed, "accept_commitment", [cid], exe))
    assert tx_execution_succeeded(send(deployed, "submit_delivery", [cid, CONTENT, j(EVID)], exe))
    assert tx_execution_succeeded(send(deployed, "close_uncontested", [cid], req))
    v = deployed.get_commitment(args=[cid]).call()
    assert v["status"] == "UNCONTESTED" and v["adjudication_id"] == ""


def test_failed_adjudication_leaves_state_unchanged(deployed, accounts):
    cid = lifecycle_to_challenged(deployed, accounts, "it-mismatch")
    tampered = CONTENT + " (tampered)"
    receipt = send(deployed, "adjudicate", [cid, tampered, j(EVID), STATEMENT, j(["C1"]), j(CH_EVID)], accounts[2])
    assert tx_execution_failed(receipt)  # deterministic hash check, before any LLM call
    v = deployed.get_commitment(args=[cid]).call()
    assert v["status"] == "CHALLENGED" and v["adjudication_id"] == ""


def test_multiple_commitments_are_independently_retrievable(deployed, accounts):
    req, exe = accounts[0], accounts[1]
    ids = []
    for n in ("it-multi-1", "it-multi-2", "it-multi-3"):
        cid = deployed.compute_commitment_id(args=[req.address, n]).call()
        assert tx_execution_succeeded(send(deployed, "create_commitment", [n, exe.address, "desc " + n, j(CRITERIA), j(KINDS)], req))
        ids.append(cid)
    assert len(set(ids)) == 3
    for n, cid in zip(("it-multi-1", "it-multi-2", "it-multi-3"), ids):
        assert deployed.get_commitment(args=[cid]).call()["description"] == "desc " + n
