# Compare Engine Package
# V2-2: Canonical-Driven Compare Engine
# V2-3: Condition & Definition Compare Engine
# V2-4: Evidence Retrieval Refinement
# V2-5: Evidence-to-Compare Binding

from compare.engine import CompareEngine, serialize_result
from compare.types import (
    CanonicalNotFoundError,
    CompareInput,
    CompareResponse,
    CompareSummary,
    CompareValue,
    DocType,
    Evidence,
    Insurer,
    InsurerResult,
    InvalidInputError,
    NoAmountResult,
    NotCoveredResult,
    ResultStatus,
    SuccessResult,
    UnknownResult,
)

# V2-4 Evidence Types
from compare.evidence_types import (
    DropReason,
    DroppedEvidence,
    EvidencePurpose,
    EvidenceSlot,
    EvidenceSlots,
    NoAmountFoundResult,
    RetrievalDebug,
    RetrievalPass,
)
from compare.evidence_retriever import (
    DocumentStore,
    EvidenceRetriever,
    EvidenceScore,
    RawEvidence,
    calculate_evidence_score,
)

# V2-5 Decision & Binding Types
from compare.decision_types import (
    BindingResult,
    BoundEvidence,
    CompareDecision,
    CompareExplanation,
    DecisionRule,
    is_determined,
    is_partial_failure,
)
from compare.evidence_binder import (
    BindingContext,
    EvidenceBinder,
    bind_evidence,
)

__all__ = [
    # Engine
    "CompareEngine",
    "serialize_result",
    # Types
    "CanonicalNotFoundError",
    "CompareInput",
    "CompareResponse",
    "CompareSummary",
    "CompareValue",
    "DocType",
    "Evidence",
    "Insurer",
    "InsurerResult",
    "InvalidInputError",
    "NoAmountResult",
    "NotCoveredResult",
    "ResultStatus",
    "SuccessResult",
    "UnknownResult",
    # V2-4 Evidence Types
    "DropReason",
    "DroppedEvidence",
    "EvidencePurpose",
    "EvidenceSlot",
    "EvidenceSlots",
    "NoAmountFoundResult",
    "RetrievalDebug",
    "RetrievalPass",
    # V2-4 Retriever
    "DocumentStore",
    "EvidenceRetriever",
    "EvidenceScore",
    "RawEvidence",
    "calculate_evidence_score",
    # V2-5 Decision & Binding
    "BindingResult",
    "BoundEvidence",
    "CompareDecision",
    "CompareExplanation",
    "DecisionRule",
    "is_determined",
    "is_partial_failure",
    "BindingContext",
    "EvidenceBinder",
    "bind_evidence",
]
