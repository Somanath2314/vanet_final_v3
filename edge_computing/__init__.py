"""
Edge Computing Module for VANET Simulation

This module provides edge computing capabilities for RSUs, including:
- Smart RSU placement at regular intervals
- Local traffic processing and analytics
- Collision avoidance services
- Emergency vehicle support
- Data aggregation and caching
- Computational offloading
"""

from .edge_rsu import EdgeRSU
from .placement.rsu_placement import RSUPlacementManager

__all__ = ['EdgeRSU', 'RSUPlacementManager']
