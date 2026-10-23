# Modified by Quantheon contributors: renamed package imports.
"""
Bucket classification utilities for SIMM sensitivity engines.

This module provides classification logic for mapping instruments to SIMM buckets
for each risk class.
"""

from quantheon_engine.simm.engines.classification.bucket_mapper import BucketMapper

__all__ = ["BucketMapper"]
