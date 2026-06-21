from fastapi import APIRouter

from klara.curriculum.competence import module_gender_progress, module_progress
from klara.curriculum.modules import read_active_module
from klara.dependencies import CurrentUser, DBSession
from klara.schemas.module import ModuleCurrentOut

router = APIRouter(prefix="/modules", tags=["modules"])


@router.get("/current", response_model=ModuleCurrentOut | None)
async def get_current_module(db: DBSession, user: CurrentUser) -> ModuleCurrentOut | None:
    """The user's active module + progress, or null if none is active yet
    (fresh account / unseeded DB). Read-only: never initializes the pointer."""
    module = await read_active_module(db, user)
    if module is None:
        return None
    encountered, mastered, total = await module_progress(db, user_id=user.id, module_id=module.id)
    g_enc, g_mast, g_total = await module_gender_progress(db, user_id=user.id, module_id=module.id)
    return ModuleCurrentOut(
        id=module.id,
        title=module.title,
        cefr_level=module.cefr_level,
        can_dos=module.can_dos or [],
        grammatical_focus=module.grammatical_focus or [],
        encountered=encountered,
        mastered=mastered,
        total=total,
        gender_encountered=g_enc,
        gender_mastered=g_mast,
        gender_total=g_total,
    )
