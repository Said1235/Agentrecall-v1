"""DEV-ONLY STUB of genlayer.types. NOT the real SDK. See tests/harness/README.md."""
import hashlib

u8 = u16 = u32 = u64 = u256 = int


class Address:
    SIZE = 20

    def __init__(self, val):
        if isinstance(val, Address):
            raw = val._b
        elif isinstance(val, (bytes, bytearray)):
            raw = bytes(val)
        else:
            raw = bytes.fromhex(val[2:] if val.startswith("0x") else val)
        if len(raw) != 20:
            raise ValueError("address must be 20 bytes")
        self._b = raw

    @property
    def as_bytes(self):
        return self._b

    @property
    def as_hex(self):
        return "0x" + self._b.hex()

    def __eq__(self, other):
        return isinstance(other, Address) and self._b == other._b

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self._b)

    def __repr__(self):
        return "Address(%s)" % self.as_hex


Address.ZERO = Address(bytes(20))


class _KeccakStub:
    # NOTE: sha3_256 is NOT Keccak-256 (different padding). Fine for logic tests only.
    def __init__(self, data=None):
        self._h = hashlib.sha3_256(data or b"")

    def digest(self):
        return self._h.digest()

    def hexdigest(self):
        return self._h.hexdigest()


def Keccak256(initial_input=None):
    return _KeccakStub(initial_input)
