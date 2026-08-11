"""Version-2 physically interpretable software plant benchmarks.

These are declared, synthetic-calibration abstractions.  They are not identified
field models and do not support crop-yield or deployment claims.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class PlantSpec:
    name: str
    sample_period_s: float
    horizon: int
    state_names: tuple[str, ...]
    state_units: tuple[str, ...]
    control_names: tuple[str, ...]
    control_units: tuple[str, ...]
    admissible_low: np.ndarray
    admissible_high: np.ndarray
    control_low: np.ndarray
    control_high: np.ndarray
    slew_limit: np.ndarray
    provenance: str


class GreenhouseClimatePlant:
    """Two-state indoor temperature/RH benchmark, five-minute ZOH model.

    Coefficients are declared synthetic calibration around a small protected
    enclosure.  State is [degC, %RH], input is [thermal-equivalent degC,
    ventilation/humidification %RH-equivalent], disturbance [outdoor degC,
    outdoor %RH].
    """
    spec = PlantSpec(
        "greenhouse", 300.0, 12, ("indoor_temperature", "indoor_rh"),
        ("degC", "%RH"), ("thermal", "humidity_vent"),
        ("equiv_degC", "equiv_%RH"), np.array([20., 55.]),
        np.array([28., 85.]), np.array([-8., -15.]), np.array([8., 15.]),
        np.array([3., 6.]),
        "Declared synthetic calibration; stable 5-min ZOH climate abstraction, not field-identified.")
    A = np.array([[.91, .006], [.018, .86]])
    B = np.array([[.12, -.018], [.01, .16]])
    E = np.array([[.085, .002], [-.01, .12]])
    reference = np.array([24., 70.])
    disturbance_reference = np.array([24., 70.])

    @property
    def name(self): return self.spec.name
    @property
    def sample_time_s(self): return self.spec.sample_period_s
    @property
    def state_min(self): return self.spec.admissible_low
    @property
    def state_max(self): return self.spec.admissible_high
    @property
    def control_dim(self): return len(self.spec.control_names)
    def clamp_u(self, u): return self.constrain(u)
    def actuation_energy_mj(self, u):
        # Software proxy: declared equivalent actuator effort, not metered energy.
        return float(0.8*np.sum(np.abs(np.asarray(u,float))))

    def __init__(self): self.x = self.reference.copy(); self.u_prev = np.zeros(2)
    def reset(self, initial=None):
        self.x = np.array(initial if initial is not None else self.reference, float)
        self.u_prev = np.zeros(2); return self.x.copy()
    def constrain(self, u):
        u=np.clip(np.asarray(u,float),self.spec.control_low,self.spec.control_high)
        u=np.clip(u,self.u_prev-self.spec.slew_limit,self.u_prev+self.spec.slew_limit)
        return u
    def step(self,u,d,noise):
        u=self.constrain(u); self.u_prev=u.copy()
        # Affine ZOH model around the declared operating point.  Using
        # deviations avoids the physically invalid offset accumulation that
        # results from multiplying absolute temperature/RH by A and E.
        dx=self.x-self.reference; dd=np.asarray(d,float)-self.disturbance_reference
        self.x=self.reference+self.A@dx+self.B@u+self.E@dd+np.asarray(noise,float)
        self.x=np.clip(self.x,[5.,10.],[50.,100.]); return self.x.copy()
    def predict(self,x,u,d):
        return self.reference+self.A@(np.asarray(x)-self.reference)+self.B@u+self.E@(np.asarray(d)-self.disturbance_reference)


class IrrigationBucketPlant:
    """Two-layer root/deep soil-water bucket with 30-minute sampling.

    State is volumetric water content [m3/m3]; control is irrigation depth
    [mm/sample]; disturbance is [rain mm/sample, ET0 mm/sample]. Coefficients
    are synthetic loam-like benchmark values and are not a named-soil fit.
    """
    spec = PlantSpec(
        "irrigation", 1800.0, 12, ("root_vwc", "deep_vwc"),
        ("m3/m3", "m3/m3"), ("irrigation",), ("mm/sample",),
        np.array([.18,.16]), np.array([.36,.40]), np.array([0.]),
        np.array([4.]), np.array([1.5]),
        "Declared synthetic loam-like two-layer bucket; not crop/soil calibrated.")
    reference=np.array([.28,.27])
    root_depth_mm=300.; deep_depth_mm=500.; infiltration_eff=.88; drainage=.035

    @property
    def name(self): return self.spec.name
    @property
    def sample_time_s(self): return self.spec.sample_period_s
    @property
    def state_min(self): return self.spec.admissible_low
    @property
    def state_max(self): return self.spec.admissible_high
    @property
    def control_dim(self): return len(self.spec.control_names)
    def clamp_u(self, u): return self.constrain(u)
    def actuation_energy_mj(self, u):
        # Pump-energy proxy proportional to delivered depth; not a measurement.
        return float(2.5*np.sum(np.maximum(np.asarray(u,float),0.)))

    def __init__(self): self.x=self.reference.copy(); self.u_prev=np.zeros(1)
    def reset(self,initial=None):
        self.x=np.array(initial if initial is not None else self.reference,float)
        self.u_prev=np.zeros(1); return self.x.copy()
    def constrain(self,u):
        u=np.clip(np.atleast_1d(u).astype(float),self.spec.control_low,self.spec.control_high)
        u=np.clip(u,self.u_prev-self.spec.slew_limit,self.u_prev+self.spec.slew_limit)
        return u
    def step(self,u,d,noise):
        u=self.constrain(u); self.u_prev=u.copy(); rain,et0=np.asarray(d,float)
        root,deep=self.x
        percol=max(root-.32,0.)*self.drainage
        root += (self.infiltration_eff*(u[0]+rain)-et0)/self.root_depth_mm-percol
        deep += percol*self.root_depth_mm/self.deep_depth_mm
        self.x=np.clip(np.array([root,deep])+np.asarray(noise,float),[.08,.08],[.48,.48])
        return self.x.copy()
    def predict(self,x,u,d):
        root,deep=np.asarray(x,float); rain,et0=np.asarray(d,float); uu=float(np.atleast_1d(u)[0])
        percol=max(root-.32,0.)*self.drainage
        return np.clip([root+(self.infiltration_eff*(uu+rain)-et0)/self.root_depth_mm-percol,
                        deep+percol*self.root_depth_mm/self.deep_depth_mm],[.08,.08],[.48,.48])


# Stable public aliases used by the v2 experiment entry points.
GreenhousePlantV2 = GreenhouseClimatePlant
IrrigationPlantV2 = IrrigationBucketPlant


def plant_factory(name):
    return GreenhouseClimatePlant() if name=="greenhouse" else IrrigationBucketPlant()
