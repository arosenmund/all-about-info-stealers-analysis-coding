"""Python reference package for the hybrid edge classifier.

Numbered ``stage_XX_*`` subpackages follow legacy contract validation, local
crawl, ingestion, classification, and decision/reporting. Training and runtime
dependencies are introduced only after their documented phase gate.
"""

from .stage_00_authorization.contracts import ALLOWED_AUTHORIZATIONS, PRIMARY_CLASSES

__all__ = ["ALLOWED_AUTHORIZATIONS", "PRIMARY_CLASSES"]
