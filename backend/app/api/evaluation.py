from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_admin
from app.rag.evaluation import list_runs, load_run

# Read-only: runs are produced by `python -m scripts.run_evaluation` (they cost API calls),
# and this router only serves the saved result files. Admin JWT required.
router = APIRouter(prefix="/admin/evaluation", tags=["evaluation"], dependencies=[Depends(require_admin)])


@router.get("/runs")
def runs() -> list[dict[str, Any]]:
    return list_runs()


@router.get("/runs/{run_id}")
def run(run_id: str) -> dict[str, Any]:
    result = load_run(run_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evaluation run not found")
    return result
