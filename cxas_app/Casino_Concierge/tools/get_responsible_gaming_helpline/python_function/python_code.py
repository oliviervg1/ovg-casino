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
get_responsible_gaming_helpline - Tool definition

PURPOSE:
    Returns the appropriate responsible gaming helpline name and phone number
    based on the active locale or language code. This isolates the configuration
    details from the Safety Handler system instructions.
"""

def get_responsible_gaming_helpline(locale: str = "") -> dict:
    """Retrieves the responsible gaming helpline name and phone number for a given locale.

    Args:
        locale: The active locale or language code (e.g., 'fr-FR', 'es-ES', 'en-US', 'en-GB').

    Returns:
        A dictionary containing 'helpline_name', 'helpline_phone', and 'locale'.
    """
    # Normalize the locale string to lowercase and strip whitespace
    loc = (locale or "").strip().lower()

    # Map locales to their respective helplines
    if "fr" in loc:
        # France / French
        return {
            "helpline_name": "Joueurs Info Service",
            "helpline_phone": "09 74 75 13 13",
            "locale": "fr-FR"
        }
    elif "es" in loc:
        # Spain / Spanish
        return {
            "helpline_name": "Línea de Ayuda de FEJAR",
            "helpline_phone": "900 200 225",
            "locale": "es-ES"
        }
    elif "us" in loc:
        # US English (Option A: 1-800-GAMBLER)
        return {
            "helpline_name": "National Gambling Helpline",
            "helpline_phone": "1-800-GAMBLER",
            "locale": "en-US"
        }
    else:
        # UK English (en-GB) and default fallback
        return {
            "helpline_name": "National Gambling Helpline",
            "helpline_phone": "0808 8020 133",
            "locale": "en-GB"
        }
