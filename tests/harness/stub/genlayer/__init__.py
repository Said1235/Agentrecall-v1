"""DEV-ONLY STUB of the `genlayer` package. NOT the real SDK.

It implements just enough surface (names verified in the v0.4.0-rc1 API reference)
to execute contracts/agent_recall.py in plain CPython for logic testing.
"""
from types import SimpleNamespace as _NS

from . import types  # noqa: F401


class _UserError(Exception):
    def __init__(self, data, /):
        super().__init__(data)
        self.data = data


class Return:
    def __init__(self, calldata):
        self.calldata = calldata


class ConsensusDisagreement(Exception):
    pass


class _TreeMap(dict):
    def __class_getitem__(cls, item):
        return cls


class _Contract:
    def __new__(cls, *args, **kwargs):
        inst = object.__new__(cls)
        for klass in cls.__mro__:
            for name, ann in getattr(klass, "__annotations__", {}).items():
                if isinstance(ann, type) and issubclass(ann, _TreeMap):
                    setattr(inst, name, ann())
        return inst


_state = _NS(last=None, llm_calls=0)


def _run_nondet_default(leader_fn, validator_fn, /, **kwargs):
    _state.last = (leader_fn, validator_fn)
    try:
        value = leader_fn()
        result = Return(value)
    except _UserError as err:
        result = err
    if not validator_fn(result):
        raise ConsensusDisagreement("validators disagreed")
    if isinstance(result, _UserError):
        raise result
    return value


def _exec_prompt(prompt, *, response_format="text", images=None):
    _state.llm_calls += 1
    if nondet.responder is None:
        raise RuntimeError("no LLM mock installed")
    return nondet.responder(prompt)


vm = _NS(UserError=_UserError, Return=Return, run_nondet_default=_run_nondet_default, state=_state)
nondet = _NS(exec_prompt=_exec_prompt, responder=None)
storage = _NS(allow=lambda cls: cls, TreeMap=_TreeMap)
contract = _NS(Contract=_Contract)
public = _NS(view=lambda f: f, write=lambda f: f)
message = _NS(sender_address=None, raw={"datetime": "2026-11-22T00:00:00Z"})
