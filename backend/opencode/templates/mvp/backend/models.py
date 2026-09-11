from __future__ import annotations

"""SQLAlchemy models.

The MVP Build Agent fills this module with one model per ER entity.
Keep the Base below; add models above the insertion point marker.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# __MODEL_INSERTION_POINT__