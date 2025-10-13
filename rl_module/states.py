"""
State representation for RL traffic optimization.
Adapted from RL-Traffic-optimization_CIL4sys
"""

import numpy as np
import traci
from collections import OrderedDict
from .helpers import flatten


class TrafficLightsStates:
    """Handles traffic light state encoding."""
    
    def __init__(self):
        pass

    def _binary_ohe_tl(self, tl_id):
        """Encodes traffic light state.
        Yellow and red states are considered off and all other states
        are considered on.

        "rryGyggrrGGrg" => [0, 0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1]

        See: https://sumo.dlr.de/wiki/Simulation/Traffic_Lights

        Parameters
        ----------
        tl_id: str
            ID of traffic light to encode state.

        Returns
        ----------
        encoded_state: [bool]
            Encoded light state
        """
        try:
            state = list(traci.trafficlight.getRedYellowGreenState(tl_id))
            red_lights = list("ry")
            return [0 if s in red_lights else 1 for s in state]
        except:
            return [0]

    def binary_state_ohe(self, ids):
        """Encodes traffic light states into a binary vector representation.

        Parameters
        ----------
        ids: List<String>
            List of traffic light ids to encode in state vector.

        Returns
        -------
        encoded_state: List<0|1>
             Encoded traffic light states in same order as `ids`."""
        return np.concatenate([self._binary_ohe_tl(tl_id) for tl_id in ids])

    def wait_steps(self, tl_wait_steps):
        """Returns how many steps each intersection have maintained state for.

        Parameters
        ----------
        tl_wait_steps: dict
             Dictionary encoding current state and timer for each intersection

        Returns
        -------
        encoded_state: List<Int>
             Vector encoding how many steps each intersection has maintained
             traffic light state for.
        """
        return [
            tl_wait_steps[tl_id]['timer'] for tl_id in tl_wait_steps.keys()
        ]


class VehicleStates:
    """Handles vehicle state encoding."""
    
    def __init__(self, beta):
        self.beta = beta

    def _get_odict(self, placeholder):
        return OrderedDict(
            [('vehicle_' + str(i), placeholder)
             for i in range(self.beta)])

    def _odict_to_list(self, odict):
        return list(odict.values())

    def accelerations(self, veh_accs):
        """Encodes vehicle speeds into a vector representation.

        Parameters
        ----------
        veh_accs: List<Floats>
            List of vehicle accelerations.

        Returns
        -------
        encoded_state: List<Float>
             Encoded orientations in same order as `ids`."""
        return self._odict_to_list(veh_accs)

    def speeds(self, ids):
        """Encodes vehicle speeds into a vector representation.

        Parameters
        ----------
        ids: List<String>
            List of vehicle ids to encode in speeds in vector.

        Returns
        -------
        encoded_state: List<Float>
             Encoded orientations in same order as `ids`."""
        odict = self._get_odict(0.)
        for veh_id in ids:
            try:
                odict[veh_id] = traci.vehicle.getSpeed(veh_id)
            except:
                odict[veh_id] = 0.
        return self._odict_to_list(odict)

    def orientations(self, ids):
        """Encodes vehicle orientation into a vector representation.
        The orientation for each vehicle is a 3-vector encoding the
        cartesian x and y coordinates along with an angle.

        Parameters
        ----------
        ids: List<String>
            List of vehicle ids to encode in orientation in vector.

        Returns
        -------
        encoded_state: List<Float> of length `3 * len(ids)`
             Encoded orientations in same order as `ids`."""
        odict = self._get_odict([0., 0., 0.])
        for veh_id in ids:
            try:
                x, y = traci.vehicle.getPosition(veh_id)
                angle = traci.vehicle.getAngle(veh_id)
                odict[veh_id] = [x, y, angle]
            except:
                odict[veh_id] = [0., 0., 0.]
        return flatten(self._odict_to_list(odict))

    def CO2_emissions(self, ids):
        """Encodes vehicle CO2 emissions into a vector representation.

        Parameters
        ----------
        ids: List<String>
            List of vehicle ids to encode in state vector.

        Returns
        -------
        encoded_state: List<Float>
             Encoded CO2 emissions in same order as `ids`."""
        odict = self._get_odict(0.)
        for veh_id in ids:
            try:
                odict[veh_id] = traci.vehicle.getCO2Emission(veh_id)
            except:
                odict[veh_id] = 0.
        return self._odict_to_list(odict)

    def wait_steps(self, veh_wait_steps):
        """Encodes steps vehicles spent idled into a vector representation.

        Parameters
        ----------
        veh_wait_steps: dict
            Dictionary of vehicle wait steps.

        Returns
        -------
        encoded_state: List<Float>
             Encoded wait_steps in same order as `ids`."""
        odict = self._get_odict(0.)
        for veh_id in veh_wait_steps.keys():
            odict[veh_id] = veh_wait_steps[veh_id]
        return self._odict_to_list(odict)


class States:
    """Combined state representation for traffic lights and vehicles."""
    
    def __init__(self, beta):
        self.tl = TrafficLightsStates()
        self.veh = VehicleStates(beta)
