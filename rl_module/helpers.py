"""Utility methods for RL environment."""

import numpy as np


def invert_tl_state(old_state, api="sumo"):
    """Invert state for given traffic light.
    It currently only implements conversion for the sumo light state.
    This function returns the new state string (of the same length as the
    input state), this allows for handling intersections with different
    numbers of lanes and lights elegantly.

    This function takes any sumo light state but only convets to a "green"
    or "red" state. Orange and other states are converted accordingly, see
    implementation for more detail.

    Parameters
    ----------
    old_state: str
        Traffic light state string to invert.
    api: str
        Simulator API which defines the light state format to return.
        Currently only implements the sumo traffic state format.
        (see: https://sumo.dlr.de/wiki/Simulation/Traffic_Lights#Signal_state_definitions)

    Returns
    ----------
    new_state: str
        New light state consisting of only red and green lights that
        oppose the previous state as much as possible.

    """
    if api == "sumo":
        state = old_state.replace("g", "G")
        state = state.replace("y", "r")
        state = state.replace("G", "tmp")
        state = state.replace("r", "G")
        state = state.replace("tmp", "r")
        return state
    else:
        return NotImplementedError


def flatten(l):
    """Flattens nested list.

    Parameters
    ----------
    lst: list
        Nested list to flatten.

    Returns
    -------
    Flattened list."""
    return [item for sublist in l for item in sublist]


def pad_list(lst, length, pad_with=0):
    """ Pads a list with extra elements.

    Parameters
    ----------
    lst: list
        List to pad
    length: int
        Must be greater than the length of `l`. The
        difference will be padded.
    pad_with: any
        Element to pad `l` with.

    e.g. pad_list([1,2,3], 5, 0) outputs [1,2,3,0,0]

    We use this helper to make sure that our states are of
    constant dimension even when some cars are not on the
    map (which happens when they get respawned)."""
    if len(lst) == length:
        return lst

    lst += [pad_with] * (length - len(lst))
    return lst
