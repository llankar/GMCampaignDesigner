"""Backward-compatible import path for DiceBarWindow and formatting models."""

from modules.dice.ui.bar.formatting import FormattedRoll, ResultChip, TextSegment
from modules.dice.ui.bar.window import DiceBarWindow

__all__ = ["DiceBarWindow", "TextSegment", "ResultChip", "FormattedRoll"]
