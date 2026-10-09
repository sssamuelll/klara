"""La nota la pone la dinámica, no el usuario (spec §1). `easy` no se usa."""

from klara.models.enums import ReviewRating


def nota(*, acierto: bool, pistas: int, ms: int, ms_lento: int) -> ReviewRating:
    if not acierto:
        return ReviewRating.AGAIN
    if pistas > 0 or ms > ms_lento:
        return ReviewRating.HARD
    return ReviewRating.GOOD
