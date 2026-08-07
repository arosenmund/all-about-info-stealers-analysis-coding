"""Stage 00 — legacy source metadata, schemas, limits, and contracts."""

from .contracts import ALLOWED_AUTHORIZATIONS, PRIMARY_CLASSES, ContractError

__all__ = ["ALLOWED_AUTHORIZATIONS", "PRIMARY_CLASSES", "ContractError"]
