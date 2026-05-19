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
after_model_callback - Safety_Handler

PURPOSE:
    Guarantees that every Safety_Handler turn includes the National Gambling
    Helpline digits ("0808 8020 133") in the text response before end_session
    fires. Backstop against the documented safety-text dropout on
    gemini-*-flash-live serving paths.

WHEN IT INJECTS:
    Only when the model emits end_session AND the agent has produced no text
    containing the helpline digits in the current conversational turn (across
    multiple model calls within a turn). If the model already said the
    helpline, the callback is a no-op.

LANGUAGE:
    Uses callback_context.state to look up active_language (e.g., "en-US",
    "fr-FR", "es-ES") and selects the canonical helpline text in that language.
    Falls back to English if the language is unset or unsupported.

PLATFORM GLOBALS (do NOT import):
    CallbackContext, Part, LlmResponse are auto-provided by the GECX sandbox.
"""

from typing import Optional

HELPLINE_DIGITS = "0808 8020 133"

CANONICAL_TEXT = {
    "en-US": (
        "I'm sorry to hear that; please consider calling the "
        "National Gambling Helpline at 0808 8020 133."
    ),
    "fr-FR": (
        "Je suis désolé d'entendre cela; veuillez envisager d'appeler la "
        "ligne d'aide nationale sur le jeu au 0808 8020 133."
    ),
    "es-ES": (
        "Lamento escuchar eso; por favor considere llamar a la "
        "Línea Nacional de Ayuda para el Juego al 0808 8020 133."
    ),
}


def _has_helpline_in_text(text: str) -> bool:
    return bool(text) and HELPLINE_DIGITS in text


def _agent_produced_helpline_in_turn(callback_context) -> bool:
    """Walk events backward from now until the last user message. If any
    agent event in between has text containing the helpline digits, the agent
    already said it earlier in this turn."""
    for event in reversed(callback_context.events):
        if event.is_user():
            return False
        if event.is_agent():
            for p in event.parts():
                content = p.text_or_transcript()
                if _has_helpline_in_text(content):
                    return True
    return False


def after_model_callback(callback_context: CallbackContext, llm_response: LlmResponse) -> Optional[LlmResponse]:
    # Detect end_session in this model call and whether THIS call already
    # produced text containing the helpline.
    has_end_session = False
    text_has_helpline_this_call = False

    for part in llm_response.content.parts:
        if part.has_function_call("end_session"):
            has_end_session = True
        else:
            content = part.text_or_transcript()
            if _has_helpline_in_text(content):
                text_has_helpline_this_call = True

    # If end_session isn't firing this call, no work to do.
    if not has_end_session:
        return None

    # If this call already contains helpline text, no work to do.
    if text_has_helpline_this_call:
        return None

    # Check earlier model calls in the same turn (multi-call turn defense).
    if _agent_produced_helpline_in_turn(callback_context):
        return None

    # No helpline text anywhere in the turn — inject before end_session.
    lang = callback_context.state.get("active_language", "en-US")
    injected_text = CANONICAL_TEXT.get(lang, CANONICAL_TEXT["en-US"])

    new_parts = [Part.from_text(text=injected_text)]
    new_parts.extend(llm_response.content.parts)
    return LlmResponse.from_parts(parts=new_parts)
