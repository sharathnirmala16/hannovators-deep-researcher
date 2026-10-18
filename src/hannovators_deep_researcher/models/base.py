"""Base class and shared field types for Pydantic contracts."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Probability = Annotated[float, Field(ge=0.0, le=1.0)]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ContractModel(BaseModel):
    """Strict contract: unknown fields are errors, so payload drift fails loudly."""

    model_config = ConfigDict(extra="forbid")
