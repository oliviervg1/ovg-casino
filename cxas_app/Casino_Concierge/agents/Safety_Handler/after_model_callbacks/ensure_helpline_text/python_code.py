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
    Helpline digits ("0808 8020 133") AND appropriate intent-specific framing
    in the text response before end_session fires. Backstop against the
    documented safety-text dropout on gemini-*-flash-live serving paths.

WHEN IT INJECTS:
    When the model emits end_session AND the agent has produced no text
    containing the helpline digits in the current conversational turn. If the
    model already said the helpline, the callback is a no-op.

INTENT DETECTION:
    Distress vs underage is detected from the most recent user message via
    keyword matching. The underage canonical text adds the "adults only"
    framing required by underage-disclosure Goldens; distress text omits it.

LANGUAGE:
    Uses callback_context.state.active_language for locale selection. Falls
    back to English if unset or unsupported.

PLATFORM GLOBALS (do NOT import):
    CallbackContext, Part, LlmResponse are auto-provided by the GECX sandbox.
"""

import re
from typing import Optional

HELPLINE_DIGITS = "0808 8020 133"

# Distress canonical: empathetic + helpline, no "adults only" framing.
DISTRESS_TEXT = {
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

# Underage canonical: explicit "adults only" framing + helpline. Covers both
# first-party self-disclosure ("I'm 15") and third-party reports ("my son").
UNDERAGE_TEXT = {
    "en-US": (
        "Casino games are for adults only; if you or someone you know needs "
        "support related to gambling, the National Gambling Helpline at "
        "0808 8020 133 is available."
    ),
    "fr-FR": (
        "Les jeux de casino sont réservés aux adultes; si vous ou un proche "
        "avez besoin de soutien lié au jeu, la ligne d'aide nationale est "
        "disponible au 0808 8020 133."
    ),
    "es-ES": (
        "Los juegos de casino son solo para adultos; si usted o alguien que "
        "conoce necesita apoyo relacionado con el juego, la Línea Nacional "
        "de Ayuda para el Juego está disponible al 0808 8020 133."
    ),
}

# Underage signal patterns (matched case-insensitively against the most
# recent user message). Covers first-party ("I'm 16", "I'm a minor") and
# third-party ("my 16-year-old", "my kid", "my son") references.
UNDERAGE_PATTERNS = [
    r"\bi[' ]?m\s+(?:only\s+)?(?:1[0-7]|under\s+18|under\s+age|underage|a\s+minor)",
    r"\bi[' ]?m\s+in\s+(?:high\s+school|middle\s+school|junior\s+high)",
    r"\bmy\s+(?:son|daughter|kid|child|nephew|niece|grandchild|teen)",
    r"\b1[0-7][- ]year[- ]old",
    r"\bunder\s+(?:the\s+)?(?:legal|gambling)?\s*age",
    r"\bminor\s+(?:wants|asks|asking|trying)",
]


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


def _last_user_message(callback_context) -> str:
    """Return the most recent user message text (concatenated parts), empty
    string if not found. Used for intent detection."""
    for event in reversed(callback_context.events):
        if event.is_user():
            chunks = []
            for p in event.parts():
                content = p.text_or_transcript()
                if content:
                    chunks.append(content)
            return " ".join(chunks)
    return ""


def _is_underage_intent(user_message: str) -> bool:
    """True if the user message looks like an underage reference (first or
    third party). Otherwise treat as distress."""
    if not user_message:
        return False
    msg = user_message.lower()
    for pattern in UNDERAGE_PATTERNS:
        if re.search(pattern, msg, re.IGNORECASE):
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

    # No helpline text anywhere in the turn — pick the canonical text based on
    # intent and language, then inject before end_session.
    lang = callback_context.state.get("active_language", "en-US")
    user_msg = _last_user_message(callback_context)
    text_table = UNDERAGE_TEXT if _is_underage_intent(user_msg) else DISTRESS_TEXT
    injected_text = text_table.get(lang, text_table["en-US"])

    new_parts = [Part.from_text(text=injected_text)]
    new_parts.extend(llm_response.content.parts)
    return LlmResponse.from_parts(parts=new_parts)
