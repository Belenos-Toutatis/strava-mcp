"""MCP tool registration helpers."""

from .activities import register as register_activities
from .athlete import register as register_athlete
from .gear import register as register_gear
from .merge_tool import register as register_merge

__all__ = [
    "register_activities",
    "register_athlete",
    "register_gear",
    "register_merge",
]
