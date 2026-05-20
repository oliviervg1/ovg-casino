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
    Programmatically appends the `end_session` tool call to the Safety_Handler's
    model-generated text response. This allows the prompt to remain entirely
    text-only (avoiding GECX text-dropout bugs on terminal tool calls) while
    ensuring that every turn handled by Safety_Handler correctly terminates.

PLATFORM GLOBALS (do NOT import):
    CallbackContext, Part, LlmResponse are auto-provided by the GECX sandbox.
"""

from typing import Optional


def after_model_callback(callback_context: CallbackContext, llm_response: LlmResponse) -> Optional[LlmResponse]:
    # Append the end_session tool to the response parts.
    new_parts = list(llm_response.content.parts)
    # Ensure we don't double-append end_session if the model somehow outputted it directly
    has_end_session = any(part.has_function_call("end_session") for part in llm_response.content.parts)
    if not has_end_session:
        new_parts.append(Part.from_function_call(name="end_session", args={"reason": "gambling_concerns"}))
    return LlmResponse.from_parts(parts=new_parts)
