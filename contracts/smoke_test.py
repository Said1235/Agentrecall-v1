# v0.4.0
# { "Depends": "py-genlayer:kzybg95x1gn21dw72m7hyg0maaap04n4nx55j9yt6fkdqxtz6bz0" }

import dataclasses
import json
import typing

import genlayer as gl
from genlayer.types import *

# Deployment smoke test for AgentRecall (NOT part of the product).
# Same header, same imports, same storage building blocks as contracts/agent_recall.py:
# a storage dataclass with str / Address / u32 fields, TreeMap[str, record], TreeMap[str, str],
# str-only public arguments, dict[str, typing.Any] view. Deploy this FIRST on the Studio:
#   - if it deploys but agent_recall.py does not, the problem is in agent_recall.py itself;
#   - if it also fails, the problem is the header, the runner or the Studio environment.


@gl.storage.allow
@dataclasses.dataclass
class Note:
    owner: Address
    text: str
    size: u32


class AgentRecallSmoke(gl.contract.Contract):
    notes: gl.storage.TreeMap[str, Note]
    status: gl.storage.TreeMap[str, str]

    def __init__(self):
        pass

    @gl.public.write
    def put(self, key: str, text: str) -> typing.Any:
        if key in self.notes:
            raise gl.vm.UserError("[EXPECTED] ALREADY_EXISTS")
        self.notes[key] = Note(
            owner=gl.message.sender_address,
            text=text,
            size=len(text.encode("utf-8")),
        )
        self.status[key] = "NEW"
        return key

    @gl.public.view
    def get(self, key: str) -> dict[str, typing.Any]:
        if key not in self.notes:
            raise gl.vm.UserError("[EXPECTED] NOT_FOUND")
        n = self.notes[key]
        return {"owner": n.owner.as_hex, "text": n.text, "size": n.size, "status": self.status[key]}
