"""
Reward functions for RL traffic optimization.
Adapted from RL-Traffic-optimization_CIL4sys
"""

import numpy as np
import traci


class Rewards:
    """Class providing rewards as methods allowing for easy composition of
    rewards from the RL environment classes.

    All public methods return an integer corresponding to the reward calculated
    at that time step."""

    def __init__(self, action_spec):
        """Instantiates a Reward object.

        Parameters
        ----------
        action_spec: dict
            OrderedDict of controlled traffic light IDs with their allowed
            states."""
        self.action_spec = action_spec
        self.tl_states = []  # traffic light states

    def _get_veh_ids(self):
        """Returns IDs of vehicles on the map at current time step."""
        try:
            return traci.vehicle.getIDList()
        except:
            return []

    def _get_obs_veh_ids(self):
        """Returns IDs of the beta observable vehicles on the map at current
        time step."""
        return [
            veh_id for veh_id in self._get_veh_ids()
            if 'human' in veh_id or 'vehicle' in veh_id
        ]

    def _get_controlled_tl_ids(self):
        return list(self.action_spec.keys())

    def penalize_min_speed(self, min_speed, reward=1, penalty=0):
        """This rewards the beta vehicles traveling over min_speed.

        Parameters
        ----------
        min_speed: int
            speed above which rewards are assigned
        reward: int
            reward for each vehicles traveling above the min_speed
        penalty: int
             penalty to assign to vehicles traveling under min_speed"""
        try:
            return np.sum([
                reward
                if traci.vehicle.getSpeed(veh_id) > min_speed else penalty
                for veh_id in self._get_obs_veh_ids()
            ])
        except:
            return 0

    def penalize_tl_switch(self, penalty=10):
        """This reward penalizes when a controlled traffic light switches
        before a minimum amount of time steps.

        Parameters
        ----------
        penalty: int
             penalty to assign to vehicles traveling under min_speed"""
        try:
            current_states = [
                traci.trafficlight.getRedYellowGreenState(tl_id)
                for tl_id in self._get_controlled_tl_ids()
            ]

            # Return 0 at first time step and set tl_states
            if not len(self.tl_states):
                self.tl_states = current_states
                return 0

            reward = 0
            for i, old_state in enumerate(self.tl_states):
                if old_state != current_states[i]:
                    reward -= penalty

            self.tl_states = current_states

            return reward
        except:
            return 0

    def penalize_max_emission(self, max_emission, reward=1, penalty=0):
        """This rewards the beta vehicles emitting less CO2 than a constraint.

        Parameters
        ----------
        max_emission: int
            emission level (in mg for the last time step, which is what Sumo
            outputs by default) under which rewards are assigned.
        reward: int
            reward for each vehicles emitting less than max_emission.
        penalty: int
             penalty to assign to vehicles emitting more than max_emission."""
        try:
            return np.sum([
                reward if traci.vehicle.getCO2Emission(veh_id)
                < max_emission else penalty for veh_id in self._get_veh_ids()
            ])
        except:
            return 0

    def penalize_max_acc(self, obs_veh_acc, max_acc, reward=1, penalty=0):
        """This rewards the beta vehicles accelerating less than a constraint.

        Parameters
        ----------
        obs_veh_acc: Dict<String, Float>
            Dictionary of accelerations in m/s^2.
        max_acc: float
            Absolute acceleration above which penalties are assigned.
        reward: int
            reward for each vehicles accelerating less than max_acc.
        penalty: int
             penalty to assign to vehicles traveling under max_acc"""
        s = 0
        for acc in obs_veh_acc.values():
            for t in range(len(acc)):
                if np.abs(acc[t]) < max_acc:
                    s += reward 
                else:
                    s += penalty
            
        return s

    def penalize_max_wait(self,
                          obs_veh_wait_steps,
                          max_wait,
                          reward=1,
                          penalty=0):
        """Penalizes each observable vehicle that has been idled for over
        `max_wait` timesteps.

        Parameters
        ----------
        obs_veh_wait_steps: dict<veh_id, int>
            Dictionary assigning to each observable vehicle ID the number of
            timesteps this vehicle has been idled for.
        max_wait: int
            Maximum number of timesteps a car can be idled without being penalized.
        reward: int
            reward for each vehicles being idled for less that `max_wait`.
        penalty: int
             penalty to assign to vehicles idled for more than `max_wait`.
        """
        return np.sum([
            reward if obs_veh_wait_steps.get(veh_id, 0) < max_wait else penalty
            for veh_id in self._get_obs_veh_ids()
        ])

    def mean_speed(self):
        """Returns the mean velocity for all vehicles on the simulation."""
        try:
            veh_ids = self._get_veh_ids()
            if not veh_ids:
                return 0
            speeds = [traci.vehicle.getSpeed(veh_id) for veh_id in veh_ids]
            return np.mean(speeds)
        except:
            return 0

    def mean_emission(self):
        """Returns the mean CO2 emission for all vehicles on the simulation."""
        try:
            veh_ids = self._get_veh_ids()
            if not veh_ids:
                return 0
            emission = [
                traci.vehicle.getCO2Emission(veh_id)
                for veh_id in veh_ids
            ]
            return np.mean(emission)
        except:
            return 0
