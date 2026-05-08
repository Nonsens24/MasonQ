"""Package-specific exceptions."""


class BrickworkTranspilerError(Exception):
    """Base exception for package-level failures."""


class BrickworkValidationError(BrickworkTranspilerError):
    """Raised when an internal brickwork representation violates invariants."""

