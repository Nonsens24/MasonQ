"""Public API for MasonQ brickwork transpilation.

The stable entry point is `transpile`. New code should request
`return_result=True` and work with `TranspileResult`.
"""

from .brickwork_transpiler import transpile
from .bfk_encoder import BFKQubitPreparation, encode_pattern, sample_qubit_preparations
from .exceptions import BrickworkTranspilerError, BrickworkValidationError
from .profiling import TimedResult, timed
from .resources import ResourceEstimate, estimate_resources
from .result import TranspileResult, VerificationResult
from .sparse import SparseInstructionMatrix
from ._versions import show_versions

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "transpile",
    "encode_pattern",
    "sample_qubit_preparations",
    "BFKQubitPreparation",
    "TranspileResult",
    "VerificationResult",
    "BrickworkTranspilerError",
    "BrickworkValidationError",
    "TimedResult",
    "timed",
    "ResourceEstimate",
    "estimate_resources",
    "SparseInstructionMatrix",
    "show_versions",
]
