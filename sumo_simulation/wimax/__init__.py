"""
Lightweight WiMAX (IEEE 802.16e-like) simulation primitives for VANET V2I.

Provides:
- WiMAXConfig: configuration for PHY/MAC parameters
- WiMAXPhy: basic OFDMA capacity and SNR model
- WiMAXMac: simple scheduler and KPI tracker
- WiMAXNode/BS: mobile station and base station abstractions
"""

from .config import WiMAXConfig
from .phy import WiMAXPhy
from .mac import WiMAXMac
from .node import WiMAXBaseStation, WiMAXMobileStation

__all__ = [
    "WiMAXConfig",
    "WiMAXPhy",
    "WiMAXMac",
    "WiMAXBaseStation",
    "WiMAXMobileStation",
]

