"""Registry of event sources, in de-duplication priority order (first wins)."""
from . import trpl, nps, trsite, fosh, tra, trc, chautauqua, joe, harvard, smithsonian, loc, nara, whha, amnh

ALL = [trpl, nps, trsite, fosh, tra, trc, chautauqua, joe, smithsonian, loc, nara, harvard, whha, amnh]
BY_ID = {m.SOURCE["id"]: m for m in ALL}
