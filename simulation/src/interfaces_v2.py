"""Contracts and SIL/HIL-ready transports for the v2 benchmark."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import json, socket, zlib

@dataclass(frozen=True)
class Observation:
    run_id:str; plant:str; seq:int; sample_time_ns:int; delivery_time_ns:int
    values:list[float]; exogenous_now:list[float]; quality_flags:int=0

@dataclass(frozen=True)
class Command:
    run_id:str; seq:int; based_on_observation_seq:int; issued_time_ns:int
    deadline_ns:int; values:list[float]; mode:str="normal"

@dataclass(frozen=True)
class Ack:
    packet_id:str; seq:int; received_time_ns:int; accepted:bool; reason:str

class InProcessTransport:
    def __init__(self): self.messages=[]
    def send(self,envelope): self.messages.append(dict(envelope)); return str(len(self.messages)-1)
    def poll(self,until_ns):
        out=[m for m in self.messages if m.get("delivery_time_ns",0)<=until_ns]
        self.messages=[m for m in self.messages if m not in out]; return out

class JsonlTransport:
    def __init__(self, path=None):
        self.path = path
        self.messages = []
    @staticmethod
    def encode(obj): return json.dumps(asdict(obj) if hasattr(obj,"__dataclass_fields__") else obj,sort_keys=True)
    @staticmethod
    def decode(line): return json.loads(line)
    def send(self, envelope):
        item = asdict(envelope) if hasattr(envelope,"__dataclass_fields__") else dict(envelope)
        self.messages.append(item)
        if self.path is not None:
            with open(self.path, "a", encoding="utf-8") as f: f.write(self.encode(item)+"\n")
        return str(len(self.messages)-1)
    def poll(self, until_ns):
        out=[m for m in self.messages if m.get("delivery_time_ns",0)<=until_ns]
        self.messages=[m for m in self.messages if m not in out]
        return out

def replay_commands(commands):
    """Deterministically replay commands, rejecting duplicate/stale sequence IDs."""
    seen=set(); accepted=[]
    for c in commands:
        if c.seq in seen: continue
        if c.issued_time_ns > c.deadline_ns: continue
        seen.add(c.seq); accepted.append(c.seq)
    return accepted


class UdpEnvelope:
    @staticmethod
    def pack(payload):
        body=json.dumps(payload,sort_keys=True).encode(); return body+b"|"+f"{zlib.crc32(body):08x}".encode()
    @staticmethod
    def unpack(blob):
        body,checksum=blob.rsplit(b"|",1)
        if f"{zlib.crc32(body):08x}".encode()!=checksum: raise ValueError("checksum")
        return json.loads(body)

class UdpLoopbackTransport:
    """Localhost schema/checksum adapter; SIL evidence, not physical HIL."""
    def __init__(self): self.seen=set()
    def roundtrip(self,payload):
        blob=UdpEnvelope.pack(payload); decoded=UdpEnvelope.unpack(blob)
        key=(decoded.get("run_id"),decoded.get("seq"),decoded.get("direction"))
        duplicate=key in self.seen; self.seen.add(key); decoded["duplicate"]=duplicate
        return decoded
