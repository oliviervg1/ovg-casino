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
before_model_callback - Boundary_Handler

PURPOSE:
    Deterministic dispatcher that classifies the user's boundary intent
    via keyword matching and returns a canned response + transfer_to_agent
    back to root. Bypasses the LLM entirely.

WHY:
    Ci-test iter 0 + iter 1 confirmed Boundary_Handler's LLM
    (gemini-3.1-flash-live) errors or returns empty for these single-turn
    deflection cases, triggering the CES FALLBACK_RESPONSE ("Hmm, I'm
    having trouble"). The after_model_callback cannot inject text because
    it doesn't run when the model errors before producing output.

    By emitting the response from before_model_callback, we skip the LLM
    call entirely — guaranteeing the user always sees the canned deflection
    text, regardless of model behavior. Boundary deflections are inherently
    formulaic, so the LLM's incremental contribution to phrasing was small.

CLASSIFICATION:
    Heuristic regex matching on the most recent user message, in priority
    order: AI-ID, account, win-guarantee, jailbreak, out-of-scope fallback.
    Returns appropriate canned text per language (en/fr/es).

PLATFORM GLOBALS (do NOT import):
    CallbackContext, Part, LlmResponse are auto-provided by the GECX sandbox.
"""

import re
from typing import Optional

PARENT_AGENT_NAME = "Casino_Concierge"

# Patterns and canonical responses per boundary class.
# Order matters: AI-ID checked first (most specific), out-of-scope last (catch-all).

AI_IDENTITY_PATTERNS = [
    r"\b(?:are you|you[' ]re)\s+(?:an?\s+)?(?:ai|a\s*i|robot|bot|human|real\s*person|machine|chatbot|model|llm)\b",
    r"\bwhat\s+are\s+you\b",
    r"\bare\s+you\s+real\b",
    r"\bare\s+you\s+a\s+person\b",
]

ACCOUNT_PATTERNS = [
    r"\b(?:my|the)\s+(?:account|balance)\b",
    r"\b(?:free|bonus)\s+spins?\b",
    r"\bdeposit\b",
    r"\bwithdraw(?:al)?\b",
    r"\bpayout\b",
    r"\btransfer\s+(?:money|funds)\b",
    r"\b(?:contact|talk to|speak (?:to|with))\s+(?:support|customer\s+service|a\s+human|an\s+agent)\b",
]

WIN_GUARANTEE_PATTERNS = [
    r"\bguarantee(?:d)?\s+(?:to\s+)?(?:win|rich|payout)\b",
    r"\bbest\s+(?:paying|payout|chance|odds)\s+game\b",
    r"\bhighest\s+(?:paying|payout)\b",
    r"\bsure\s+(?:thing|bet)\b",
    r"\blucky\s+strategy\b",
    r"\bbeat\s+the\s+(?:house|casino|odds)\b",
    r"\b(?:guaranteed|sure)\s+(?:to\s+)?(?:make|win)\s+(?:me\s+)?(?:rich|money)\b",
]

JAILBREAK_PATTERNS = [
    r"\bignore\s+(?:your|the|all|previous)\s+instructions\b",
    r"\bignore\s+(?:your|the|all|previous)\s+(?:prompt|system\s+prompt)\b",
    r"\bpretend\s+(?:to\s+be|you[' ]re|you\s+are)\b",
    r"\b(?:reveal|show|tell\s+me)\s+(?:your|the)\s+(?:prompt|system\s+prompt|instructions)\b",
    r"\bact\s+as\s+(?:a|an)\b",
    r"\bbreak\s+character\b",
]

CANONICAL_RESPONSES = {
    "ai_identity": {
        "en-US": (
            "Yes, I'm an AI Casino Concierge, here to help you find a great game. "
            "Want me to suggest something?"
        ),
        "fr-FR": (
            "Oui, je suis un Concierge de casino IA, là pour vous aider à trouver "
            "un jeu génial. Voulez-vous une suggestion?"
        ),
        "es-ES": (
            "Sí, soy un Concierge de casino con IA, aquí para ayudarte a encontrar "
            "un gran juego. ¿Quieres que te recomiende algo?"
        ),
    },
    "account": {
        "en-US": (
            "I'm not able to access account information or provide free spins, "
            "but I'd love to help you find a great game. What kind of experience "
            "are you looking for?"
        ),
        "fr-FR": (
            "Je ne peux pas accéder aux informations de compte ni offrir des "
            "tours gratuits, mais je peux vous aider à trouver un super jeu. "
            "Quel genre d'expérience cherchez-vous?"
        ),
        "es-ES": (
            "No puedo acceder a la información de la cuenta ni dar tiradas gratis, "
            "pero me encantaría ayudarte a encontrar un gran juego. ¿Qué tipo de "
            "experiencia buscas?"
        ),
    },
    "win_guarantee": {
        "en-US": (
            "All of our games are based on chance, so I can't guarantee any wins. "
            "Games are for entertainment and fun — would you like a recommendation "
            "based on theme or style?"
        ),
        "fr-FR": (
            "Tous nos jeux sont basés sur le hasard, donc je ne peux garantir aucun "
            "gain. Les jeux sont là pour le divertissement — voulez-vous une "
            "recommandation par thème ou par style?"
        ),
        "es-ES": (
            "Todos nuestros juegos se basan en el azar, así que no puedo garantizar "
            "ganancias. Los juegos son para divertirse — ¿quieres una recomendación "
            "por tema o estilo?"
        ),
    },
    "jailbreak": {
        "en-US": (
            "I can't share that, but I'd love to keep helping you find a great game. "
            "Are you in the mood for Roulette, Slots, or Bingo?"
        ),
        "fr-FR": (
            "Je ne peux pas partager cela, mais je peux continuer à vous aider à "
            "trouver un super jeu. Préférez-vous la Roulette, les Machines à sous "
            "ou le Bingo?"
        ),
        "es-ES": (
            "No puedo compartir eso, pero me encantaría seguir ayudándote a encontrar "
            "un gran juego. ¿Te apetece Ruleta, Tragamonedas o Bingo?"
        ),
    },
    "out_of_scope": {
        "en-US": (
            "My expertise is focused on casino game recommendations and explanations, "
            "so I can't help with that. Would you like me to recommend a game?"
        ),
        "fr-FR": (
            "Mon expertise concerne les recommandations et explications de jeux de "
            "casino, donc je ne peux pas aider avec cela. Voulez-vous une "
            "recommandation de jeu?"
        ),
        "es-ES": (
            "Mi especialidad son las recomendaciones y explicaciones de juegos de "
            "casino, así que no puedo ayudar con eso. ¿Quieres que te recomiende "
            "un juego?"
        ),
    },
}


def _last_user_message(callback_context) -> str:
    for event in reversed(callback_context.events):
        if event.is_user():
            chunks = []
            for p in event.parts():
                content = p.text_or_transcript()
                if content:
                    chunks.append(content)
            return " ".join(chunks)
    return ""


def _classify(user_message: str) -> str:
    """Classify the boundary intent. Returns one of:
    ai_identity, account, win_guarantee, jailbreak, out_of_scope."""
    if not user_message:
        return "out_of_scope"
    msg = user_message.lower()
    for pat in AI_IDENTITY_PATTERNS:
        if re.search(pat, msg, re.IGNORECASE):
            return "ai_identity"
    for pat in ACCOUNT_PATTERNS:
        if re.search(pat, msg, re.IGNORECASE):
            return "account"
    for pat in WIN_GUARANTEE_PATTERNS:
        if re.search(pat, msg, re.IGNORECASE):
            return "win_guarantee"
    for pat in JAILBREAK_PATTERNS:
        if re.search(pat, msg, re.IGNORECASE):
            return "jailbreak"
    return "out_of_scope"


def before_model_callback(callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
    user_msg = _last_user_message(callback_context)
    category = _classify(user_msg)
    lang = callback_context.state.get("active_language", "en-US")
    text = CANONICAL_RESPONSES[category].get(lang, CANONICAL_RESPONSES[category]["en-US"])

    return LlmResponse.from_parts(parts=[
        Part.from_text(text=text),
        Part(function_call=Part.FunctionCall(
            name="transfer_to_agent",
            args={"agent": PARENT_AGENT_NAME},
        )),
    ])
