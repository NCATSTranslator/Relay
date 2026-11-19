"""Garbage-collector thresholds for the ARS web and worker processes.

Parsing and merging large TRAPI responses creates millions of dicts and lists.
Benchmarking showed that performance can be significantly improved by tuning the 
frequency that python attempts to run garbage collection during that process.
This module allows us to set the GC thresholds with an environment variable,
with default values that were shown to increase speed.

Using the ARS_GC_THRESHOLD environment variable:

    unset or empty      use DEFAULT_GC_THRESHOLD
    "g0,g1,g2"          three positive integers, passed to gc.set_threshold
    "off"               leave Python's thresholds as they are

A value that cannot be parsed is logged and treated as "off", so a typo can never apply
thresholds nobody chose.
"""
import gc
import logging
import os

logger = logging.getLogger(__name__)

ENV_VAR = 'ARS_GC_THRESHOLD'
DEFAULT_GC_THRESHOLD = (100000, 50, 100)
OFF_VALUES = ('off', 'false', 'no', 'none', 'default', 'disabled')


def parse_gc_threshold(value):
    """Return the (g0, g1, g2) thresholds to apply, or None to leave Python's alone."""
    if value is None or not value.strip():
        return DEFAULT_GC_THRESHOLD
    value = value.strip()
    if value.lower() in OFF_VALUES:
        return None
    try:
        thresholds = tuple(int(part) for part in value.split(','))
    except ValueError:
        thresholds = ()
    if len(thresholds) != 3 or any(t <= 0 for t in thresholds):
        logger.warning('%s=%r is not "off" or three positive integers; '
                       'leaving the garbage collector thresholds unchanged', ENV_VAR, value)
        return None
    return thresholds


def apply_gc_threshold():
    """Set this process's thresholds from the environment. Returns what was applied."""
    thresholds = parse_gc_threshold(os.environ.get(ENV_VAR))
    if thresholds is None:
        logger.info('garbage collector thresholds left at %s', gc.get_threshold())
        return None
    gc.set_threshold(*thresholds)
    logger.info('garbage collector thresholds set to %s', thresholds)
    return thresholds