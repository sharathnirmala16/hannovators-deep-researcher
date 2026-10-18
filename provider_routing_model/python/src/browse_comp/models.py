"""Data models for benchmark inputs and reference answers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BenchmarkCase(BaseModel):
    """Execution input case accepted by the provider evals harness.

    The harness strictly rejects unknown fields, including answers.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, description="Unique case identifier.")
    prompt: str = Field(min_length=1, description="Task prompt for the agent.")
    requiredTools: list[Literal["search", "fetch"]] | None = Field(
        default=None,
        description="Optional list of required tool names.",
    )


class BenchmarkAnswer(BaseModel):
    """Ground truth answer record kept separate from benchmark execution."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, description="Case identifier matching benchmark input.")
    answer: str = Field(description="Decrypted reference ground truth answer.")
    problem_topic: str = Field(description="Topic category of the question.")
    prompt: str = Field(description="Original question prompt for context during scoring.")
