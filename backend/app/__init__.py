"""AI Voice Studio backend.

The model-agnostic inference layer lives in the repository-root ``ai/`` package
(kept out of ``backend/`` so it can be reused by a standalone GPU worker later
without dragging the web layer along). When the backend is started from
``backend/`` -- ``uvicorn app.main:app`` -- that root is not on ``sys.path``, so
we add it here. Installing the project as a package would be the alternative;
this keeps ``pip install -r requirements.txt && uvicorn app.main:app`` working
with no build step.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if (_REPO_ROOT / "ai" / "__init__.py").is_file() and str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

__version__ = "0.1.0"
