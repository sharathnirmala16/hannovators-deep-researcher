"""Domain enums shared by the database, the pipeline, the HTTP API, and the frontend."""

from enum import StrEnum


class DomainMode(StrEnum):
    """Resolved research domain. It selects PICOTS (MEDICAL) or scope (GENERAL) decomposition."""

    MEDICAL = "MEDICAL"
    GENERAL = "GENERAL"


class RequestedDomainMode(StrEnum):
    """Domain mode a request can ask for. AUTO stays on the workspace until decompose sets it."""

    MEDICAL = "MEDICAL"
    GENERAL = "GENERAL"
    AUTO = "AUTO"


class WorkspaceStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StageId(StrEnum):
    """Pipeline stages in run order."""

    INGEST = "ingest"
    DECOMPOSE = "decompose"
    SEARCH = "search"
    SCREEN = "screen"
    ACQUIRE = "acquire"
    APPRAISE = "appraise"
    SYNTHESIZE = "synthesize"
    HIGHLIGHT = "highlight"
    COMPOSE = "compose"


class SourceOrigin(StrEnum):
    SEED = "SEED"
    PUBMED = "PUBMED"
    EUROPEPMC = "EUROPEPMC"
    WEB = "WEB"


class SourceStatus(StrEnum):
    SEED = "SEED"
    RAW = "RAW"
    SCREEN_PROMOTED = "SCREEN_PROMOTED"
    SCREEN_DISCOUNTED = "SCREEN_DISCOUNTED"
    APPRAISE_PROMOTED = "APPRAISE_PROMOTED"
    APPRAISE_DISCOUNTED = "APPRAISE_DISCOUNTED"
    ACQUIRE_FAILED = "ACQUIRE_FAILED"


class RejectionCode(StrEnum):
    LOW_RELEVANCE = "LOW_RELEVANCE"
    VOTES_BELOW_T = "VOTES_BELOW_T"
    M_BELOW_THRESHOLD = "M_BELOW_THRESHOLD"
    ANIMAL_STUDY = "ANIMAL_STUDY"
    REVIEW_OR_EDITORIAL = "REVIEW_OR_EDITORIAL"
    OFF_TOPIC = "OFF_TOPIC"
    DUPLICATE = "DUPLICATE"
    NO_FULL_TEXT = "NO_FULL_TEXT"
    UNDERPOWERED = "UNDERPOWERED"
    LOW_CREDIBILITY = "LOW_CREDIBILITY"


class Directness(StrEnum):
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"


class RobJudgement(StrEnum):
    """Official RoB 2 judgement levels."""

    LOW = "LOW"
    SOME_CONCERNS = "SOME_CONCERNS"
    HIGH = "HIGH"


class GradeCertainty(StrEnum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"


class ClaimKind(StrEnum):
    METRIC = "METRIC"
    CLAIM = "CLAIM"
    RECOMMENDATION = "RECOMMENDATION"


class ClaimVerdict(StrEnum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    MIXED = "MIXED"
    UNVERIFIED = "UNVERIFIED"


class ClaimArm(StrEnum):
    INTERVENTION = "INTERVENTION"
    COMPARISON = "COMPARISON"


class UiComponentId(StrEnum):
    SCOPE_BUILDER = "scope_builder"
    SCREENING_FUNNEL = "screening_funnel"
    EVIDENCE_PROFILE_TABLE = "evidence_profile_table"
    CLAIM_MATRIX = "claim_matrix"
    SYNTHESIS_PANEL = "synthesis_panel"
    PDF_VIEWER = "pdf_viewer"
    CITATION_GRAPH = "citation_graph"


class TraceEventKind(StrEnum):
    STAGE_STARTED = "STAGE_STARTED"
    STAGE_COMPLETED = "STAGE_COMPLETED"
    STAGE_FAILED = "STAGE_FAILED"
    PROGRESS = "PROGRESS"
    QUERY = "QUERY"
    DECISION = "DECISION"
    WARNING = "WARNING"
    STATUS = "STATUS"


class ModelRole(StrEnum):
    """Agent model roles. Each role can override the model ID with MODEL_<ROLE>."""

    DECOMPOSE = "DECOMPOSE"
    QUERY = "QUERY"
    APPRAISE = "APPRAISE"
    EXTRACT_VISION = "EXTRACT_VISION"
    SYNTHESIZE = "SYNTHESIZE"


class ChunkTier(StrEnum):
    ABSTRACT = "ABSTRACT"
    FULLTEXT = "FULLTEXT"


class SourceLinkKind(StrEnum):
    CITES = "CITES"
    RELATED = "RELATED"
    SEED_MATCH = "SEED_MATCH"


class HighlightMethod(StrEnum):
    SEARCH = "SEARCH"
    JEV_CHOICE = "JEV_CHOICE"


class RecommendationDirection(StrEnum):
    FOR = "FOR"
    AGAINST = "AGAINST"
    NONE = "NONE"


class RecommendationStrength(StrEnum):
    STRONG = "STRONG"
    CONDITIONAL = "CONDITIONAL"


class DecisionQuestionType(StrEnum):
    """Jev System One question types."""

    CHOICE = "choice"
    SCORE = "score"
    NOUL = "noul"


class ProviderAttemptStatus(StrEnum):
    """Outcome of one provider attempt inside a routed web search."""

    OK = "OK"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class EvidenceLevel(StrEnum):
    """Study design on the evidence hierarchy. `EVIDENCE_RANK` orders it (1 = strongest)."""

    META_ANALYSIS = "META_ANALYSIS"
    SYSTEMATIC_REVIEW = "SYSTEMATIC_REVIEW"
    RCT = "RCT"
    NON_RANDOMIZED_TRIAL = "NON_RANDOMIZED_TRIAL"
    COHORT = "COHORT"
    CASE_CONTROL = "CASE_CONTROL"
    CROSS_SECTIONAL = "CROSS_SECTIONAL"
    CASE_SERIES = "CASE_SERIES"
    GUIDELINE = "GUIDELINE"
    NARRATIVE_REVIEW = "NARRATIVE_REVIEW"
    PRECLINICAL = "PRECLINICAL"
    WEB_REPORT = "WEB_REPORT"
    OTHER = "OTHER"


EVIDENCE_RANK: dict[EvidenceLevel, int] = {
    EvidenceLevel.META_ANALYSIS: 1,
    EvidenceLevel.SYSTEMATIC_REVIEW: 2,
    EvidenceLevel.RCT: 3,
    EvidenceLevel.GUIDELINE: 4,
    EvidenceLevel.NON_RANDOMIZED_TRIAL: 5,
    EvidenceLevel.COHORT: 6,
    EvidenceLevel.CASE_CONTROL: 7,
    EvidenceLevel.CROSS_SECTIONAL: 8,
    EvidenceLevel.CASE_SERIES: 9,
    EvidenceLevel.NARRATIVE_REVIEW: 10,
    EvidenceLevel.WEB_REPORT: 11,
    EvidenceLevel.PRECLINICAL: 12,
    EvidenceLevel.OTHER: 13,
}


class EvidenceStance(StrEnum):
    """What a source says about the research question."""

    SUPPORTS = "SUPPORTS"
    OPPOSES = "OPPOSES"
    NULL_RESULT = "NULL_RESULT"
    MIXED = "MIXED"
    ALTERNATIVE = "ALTERNATIVE"
    UNCLEAR = "UNCLEAR"


class SearchIntent(StrEnum):
    """Why a query was run. NEGATIVE and ALTERNATIVE keep the agent looking for disconfirming
    evidence and other options, not only for support."""

    CORE = "CORE"
    NEGATIVE = "NEGATIVE"
    ALTERNATIVE = "ALTERNATIVE"
    SAFETY = "SAFETY"
    SEED_CITATION = "SEED_CITATION"
    DEEP_RESEARCH = "DEEP_RESEARCH"


class TrajectoryActor(StrEnum):
    AGENT = "AGENT"
    USER = "USER"
    SYSTEM = "SYSTEM"


class TrajectoryKind(StrEnum):
    """One row type in the trajectory (network-tab) view."""

    STAGE = "STAGE"
    LLM = "LLM"
    DECISION = "DECISION"
    SEARCH = "SEARCH"
    FETCH = "FETCH"
    DOWNLOAD = "DOWNLOAD"
    EMBED = "EMBED"
    RETRIEVE = "RETRIEVE"
    VERDICT = "VERDICT"
    USER_ACTION = "USER_ACTION"
    CHAT = "CHAT"


class TrajectoryStatus(StrEnum):
    RUNNING = "RUNNING"
    OK = "OK"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


class VerdictOutcome(StrEnum):
    """What a VERDICT step decided about a source or claim."""

    KEPT = "KEPT"
    REMOVED = "REMOVED"
    FLAGGED = "FLAGGED"


class ChatRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
