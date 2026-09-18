"""
SweetAstro Chat Layer — conversational front-end for the Consumer Answer Engine.

Pipeline per user turn:
  1. Extract birth facts + question from the conversation (DeepSeek JSON mode).
  2. Compute the chart deterministically (SweetAstro core / consumer engine).
  3. Feed the verified payload to DeepSeek Flash for the calibrated 16-section answer.
"""

from .client import DeepSeekClient, DeepSeekError
from .session import BirthSlots, ChatSession, SessionStore
from .orchestrator import ChatEvent, ChatOrchestrator

__all__ = [
    "DeepSeekClient",
    "DeepSeekError",
    "BirthSlots",
    "ChatSession",
    "SessionStore",
    "ChatEvent",
    "ChatOrchestrator",
]
