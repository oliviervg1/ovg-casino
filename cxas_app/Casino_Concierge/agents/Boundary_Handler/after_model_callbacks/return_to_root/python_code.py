# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
after_model_callback - Boundary_Handler

PURPOSE:
    Two responsibilities:
    1. Guarantee Boundary_Handler emits ANY text response. If the model
       drops text (live-streaming dropout pathology), inject a generic
       polite-redirect fallback so the user doesn't see the CES system
       fallback ("Hmm, I'm having trouble...").
    2. Unconditionally transfer control back to the parent root agent
       (Casino_Concierge) after the response so subsequent user turns
       land on root.

WHY THE FALLBACK INJECTION:
    Ci-test confirmed Boundary_Handler on gemini-3.1-flash-live exhibits
    the same text dropout class as Safety_Handler did pre-callback. Empty
    response from sub-agent triggers CES's FALLBACK_RESPONSE strategy,
    which returns a generic "having trouble" message — a worse UX than
    a generic redirect.

LANGUAGE:
    Uses callback_context.state.active_language for fallback text. Falls
    back to English if unset or unsupported.

PLATFORM GLOBALS (do NOT import):
    CallbackContext, Part, LlmResponse are auto-provided by the GECX sandbox.
"""

from typing import Optional

PARENT_AGENT_NAME = "Casino_Concierge"

FALLBACK_TEXT = {
    "en-US": (
        "I'm here to help you find a great casino game. "
        "What kind would you like — Roulette, Slots, or Bingo?"
    ),
    "fr-FR": (
        "Je suis là pour vous aider à trouver un jeu de casino. "
        "Que préférez-vous — Roulette, Machines à sous, ou Bingo?"
    ),
    "es-ES": (
        "Estoy aquí para ayudarte a encontrar un gran juego de casino. "
        "¿Qué tipo prefieres — Ruleta, Tragamonedas o Bingo?"
    ),
}


def _has_any_text(parts) -> bool:
    """True if any part has non-empty text/transcript content."""
    for p in parts:
        content = p.text_or_transcript()
        if content and content.strip():
            return True
    return False


def after_model_callback(callback_context: CallbackContext, llm_response: LlmResponse) -> Optional[LlmResponse]:
    existing_parts = list(llm_response.content.parts)

    # If the model produced no text, inject a fallback redirect so the user
    # doesn't see the CES "having trouble" system fallback when sub-agent
    # response is empty.
    if not _has_any_text(existing_parts):
        lang = callback_context.state.get("active_language", "en-US")
        fallback = FALLBACK_TEXT.get(lang, FALLBACK_TEXT["en-US"])
        existing_parts = [Part.from_text(text=fallback)] + existing_parts

    # Append a deterministic transfer back to the root agent. CES processes
    # the transfer at end of turn; the next user turn starts on root.
    transfer_part = Part(function_call=Part.FunctionCall(
        name="transfer_to_agent",
        args={"agent": PARENT_AGENT_NAME},
    ))

    return LlmResponse.from_parts(parts=existing_parts + [transfer_part])
