"""Lume engine - deterministic control layer for the iteration loop.

No module here performs inference or network I/O; the engine only reads,
parses, and writes on-disk workstream state. Inference is reserved for the
work an iteration contains, never the mechanism that runs it.
"""
