"""Appraise edge case: a quote that is not in the abstract is marked UNVERIFIED."""

import pytest

from hannovators_deep_researcher.models.enums import ClaimVerdict, Directness
from hannovators_deep_researcher.services.pipeline.stages.appraise import medical

pytestmark = pytest.mark.unit

ABSTRACT = "RESULTS: Death occurred in 2/70   patients vs 8/53 with placebo."


def test_quote_not_in_abstract_is_unverified() -> None:
    reply = medical.MedicalAppraisal.model_validate(medical.MedicalAppraisal.fake_example())
    real, invented = reply.metrics[0], reply.metrics[0]
    reply.metrics = [
        real.model_copy(update={"quote": "death occurred in 2/70 patients"}),
        invented.model_copy(update={"quote": "mortality fell by 75%"}),
    ]

    result = medical.evaluate("s1", ABSTRACT, reply, threshold=3)

    assert [claim.verdict for claim in result.claims] == [
        ClaimVerdict.SUPPORTED,
        ClaimVerdict.UNVERIFIED,
    ]
    assert result.directness == Directness.INDIRECT
