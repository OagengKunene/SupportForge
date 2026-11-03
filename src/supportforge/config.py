"""Explicit configuration. No API key is needed for the default demo mode."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

PACKAGE_ROOT = Path(__file__).parent


@dataclass(frozen=True)
class Settings:
    mode: Literal["demo", "openai"] = "demo"
    database: Path = Path("data/supportforge.sqlite3")
    knowledge_dir: Path = PACKAGE_ROOT / "sample_knowledge"
    api_token: str = field(default="", repr=False)
    openai_api_key: str = field(default="", repr=False)
    model: str = "gpt-4o-mini"
    model_timeout: float = 45.0

    def __post_init__(self):
        if self.mode not in {"demo", "openai"}:
            raise ValueError("SUPPORTFORGE_MODE must be demo or openai")
        if self.mode == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required in openai mode")
        if self.model_timeout <= 0:
            raise ValueError("Model timeout must be positive")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            mode=os.getenv("SUPPORTFORGE_MODE", "demo"),
            database=Path(os.getenv("SUPPORTFORGE_DATABASE", "data/supportforge.sqlite3")),
            knowledge_dir=Path(
                os.getenv("SUPPORTFORGE_KNOWLEDGE_DIR", str(PACKAGE_ROOT / "sample_knowledge"))
            ),
            api_token=os.getenv("SUPPORTFORGE_API_TOKEN", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            model_timeout=float(os.getenv("SUPPORTFORGE_MODEL_TIMEOUT", "45")),
        )
