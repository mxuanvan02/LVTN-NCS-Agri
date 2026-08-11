"""Deterministic two-way packet/network emulator for the v2 benchmark.

All random tokens are addressed by immutable keys.  Consequently policies that
send different numbers of packets still see the same exogenous realization for
a given logical sample/attempt.  Values are benchmark stress assumptions, not a
standards-compliant radio or a field measurement.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import numpy as np


class RandomTape:
    def __init__(self, seed: int, plant: str, profile: str):
        self.seed, self.plant, self.profile = int(seed), plant, profile
    def _seed(self, *key) -> int:
        s = ":".join(map(str, (self.seed, self.plant, self.profile, *key)))
        return int.from_bytes(hashlib.sha256(s.encode()).digest()[:8], "little")
    def uniform(self, *key) -> float:
        return float(np.random.default_rng(self._seed(*key)).random())
    def normal(self, *key, scale=1.0) -> float:
        return float(np.random.default_rng(self._seed(*key)).normal(0.0, scale))
    def sha256(self) -> str:
        return hashlib.sha256(f"{self.seed}:{self.plant}:{self.profile}".encode()).hexdigest()


@dataclass(frozen=True)
class NetworkProfile:
    name: str
    uplink_delay_s: float = 0.0
    downlink_delay_s: float = 0.0
    jitter_s: float = 0.0
    uplink_loss: float = 0.0
    downlink_loss: float = 0.0
    bandwidth_bps: float = 1e9
    background_utilization: float = 0.0
    queue_limit: int = 64
    duty_fraction: float = 1.0
    ack_loss: float = 0.0
    ack_timeout_s: float = 0.0
    max_retries: int = 0
    compute_latency_s: float = 0.0
    burst: bool = False


PROFILES = {
 "N0_ideal": NetworkProfile("N0_ideal"),
 "N1_nominal": NetworkProfile("N1_nominal",1,1,.5,.05,.02,50_000,.20,64,1,.01,.5,1,.08),
 "N2_iid_loss": NetworkProfile("N2_iid_loss",1,1,.5,.20,.10,50_000,.20,64,1,.02,.5,1,.08),
 "N3_burst_loss": NetworkProfile("N3_burst_loss",1,1,.5,.20,.10,50_000,.20,64,1,.02,.5,1,.08,True),
 "N4_contention_duty": NetworkProfile("N4_contention_duty",2,2,1,.05,.05,10_000,.70,8,.10,.08,1,2,.15),
 "N5_full_stress": NetworkProfile("N5_full_stress",5,5,3,.20,.10,10_000,.70,8,.05,.10,2,2,.35,True),
}


@dataclass
class PacketEvent:
    packet_id: str; parent_packet_id: str; direction: str; attempt_no: int
    sample_seq: int; sensor_timestamp: float; enqueue_timestamp: float
    tx_start: float; tx_end: float; arrival_timestamp: float; deadline: float
    payload_bytes: int; queue_depth: int; loss_cause: str; duplicate: bool
    accepted: bool


class NetworkEmulator:
    def __init__(self, profile: NetworkProfile, tape: RandomTape):
        self.p, self.tape = profile, tape
        self.next_free = {"uplink": 0.0, "downlink": 0.0, "ack": 0.0}
        self.seen = set()
    def _burst_loss(self, direction, seq, attempt, base):
        if not self.p.burst: return self.tape.uniform(direction,seq,attempt,"loss") < base
        # Keyed four-attempt blocks give reproducible burst correlation without
        # policy-dependent RNG consumption.
        bad = self.tape.uniform(direction, seq//4, "burst") < min(.55, base*2.2)
        prob = min(.92, base*2.8) if bad else max(.01, base*.35)
        return self.tape.uniform(direction,seq,attempt,"loss") < prob
    def _send(self, direction, seq, now, nbytes, deadline, attempt, parent):
        p=self.p; serialization=8*nbytes/max(p.bandwidth_bps,1.)
        contention=(p.background_utilization/(1-p.background_utilization+1e-9))*serialization
        contention*=self.tape.uniform(direction,seq,attempt,"contention")
        duty_wait=0.0
        if p.duty_fraction < 1:
            duty_wait=serialization*(1/p.duty_fraction-1)*self.tape.uniform(direction,seq,attempt,"duty")
        start=max(now,self.next_free[direction])+contention+duty_wait
        end=start+serialization; self.next_free[direction]=end
        delay=p.uplink_delay_s if direction=="uplink" else p.downlink_delay_s
        jitter=max(0.,self.tape.normal(direction,seq,attempt,"jitter",scale=p.jitter_s))
        arrival=end+delay+jitter
        base=p.uplink_loss if direction=="uplink" else p.downlink_loss
        lost=self._burst_loss(direction,seq,attempt,base)
        cause="burst" if lost and p.burst else ("Bernoulli" if lost else "none")
        if start-now > p.queue_limit*serialization: lost=True; cause="queue"
        if arrival>deadline: lost=True; cause="deadline"
        pid=f"{parent}:{direction}:{attempt}"; duplicate=parent in self.seen
        if not lost: self.seen.add(parent)
        ev=PacketEvent(pid,parent,direction,attempt,seq,now,now,start,end,arrival,deadline,nbytes,0,cause,duplicate,not lost)
        return ev
    def transact(self, seq: int, payload_bytes: int, deadline_s: float, compute_family: str, now_s: float | None = None):
        p=self.p; now=float(seq if now_s is None else now_s); origin=now; absolute_deadline=origin+deadline_s
        logs=[]; energy={k:0. for k in ("tx","rx","listen","retry")}
        uplink=None
        for attempt in range(p.max_retries+1):
            ev=self._send("uplink",seq,now,payload_bytes,absolute_deadline,attempt,f"obs-{seq}"); logs.append(ev)
            airtime=ev.tx_end-ev.tx_start; energy["tx"]+=20*airtime+1.2; energy["listen"]+=.35
            if attempt: energy["retry"]+=1.2
            if ev.accepted: uplink=ev; break
            now=ev.arrival_timestamp+p.ack_timeout_s
        if uplink is None: return False, max(x.arrival_timestamp for x in logs)-origin, logs, energy
        compute=p.compute_latency_s*(1.5 if compute_family=="MPC" else .5)
        now=uplink.arrival_timestamp+compute
        down=self._send("downlink",seq,now,32,absolute_deadline,0,f"cmd-{seq}"); logs.append(down)
        energy["rx"]+=.8; energy["listen"]+=.25
        ack_lost=self.tape.uniform("ack",seq,"loss") < p.ack_loss
        if down.accepted and ack_lost:
            # Duplicate retry is logged and charged, but actuator idempotence
            # means only the first logical command is accepted.
            dup=self._send("downlink",seq,down.arrival_timestamp+p.ack_timeout_s,32,absolute_deadline,1,f"cmd-{seq}")
            dup.duplicate=True; dup.accepted=False; dup.loss_cause="duplicate"; logs.append(dup); energy["retry"]+=1.2
        ok=down.accepted
        latency=max(x.arrival_timestamp for x in logs)-origin
        return ok,latency,logs,energy
