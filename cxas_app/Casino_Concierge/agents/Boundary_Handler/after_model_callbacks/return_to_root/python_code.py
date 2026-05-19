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
    Unconditionally returns control to the parent agent (Casino_Concierge)
    after every Boundary_Handler model call. The user's deflection response
    is preserved in the output; subsequent user turns land on root.

WHY:
    Boundary deflections are inherently single-turn (AI identity, win-
    guarantee denial, jailbreak refusal, out-of-scope deflection). Without
    this callback, the user would stay on Boundary_Handler for follow-up
    turns where they can't be helped (no tools, no domain instructions).

HOW:
    Emits a transfer_to_agent function call alongside the model's existing
    text/parts. CES processes the transfer at end of turn; next turn starts
    on the root agent.

PLATFORM GLOBALS (do NOT import):
    CallbackContext, Part, LlmResponse are auto-provided by the GECX sandbox.
"""

from typing import Optional

PARENT_AGENT_NAME = "Casino_Concierge"


def after_model_callback(callback_context: CallbackContext, llm_response: LlmResponse) -> Optional[LlmResponse]:
    # Preserve everything the model produced (typically just text) and append
    # a deterministic transfer back to the root agent.
    existing_parts = list(llm_response.content.parts)

    transfer_part = Part(function_call=Part.FunctionCall(
        name="transfer_to_agent",
        args={"agent": PARENT_AGENT_NAME},
    ))

    return LlmResponse.from_parts(parts=existing_parts + [transfer_part])
