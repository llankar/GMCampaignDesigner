from modules.generic.editor.window_context import *
from modules.campaigns.services.tone_contract import format_tone_contract_guidance, load_campaign_tone_contract


class GenericEditorWindowAIFieldAssistance:
    def _tone_contract_guidance(self):
        contract = load_campaign_tone_contract()
        if not contract:
            return ""
        return format_tone_contract_guidance(contract)

    def _field_text(self, field_name):
        widget = self.field_widgets.get(field_name)
        if hasattr(widget, "text_widget"):
            return widget.text_widget.get("1.0", "end").strip()
        return str(self.item.get(field_name, ""))
    def _set_field_text(self, field_name, text):
        widget = self.field_widgets.get(field_name)
        if hasattr(widget, "text_widget"):
            # Try to interpret AI markdown-like formatting into RTF-JSON
            try:
                rtf = ai_text_to_rtf_json(text)
                widget.load_text_data(rtf)
            except Exception:
                widget.text_widget.delete("1.0", "end")
                widget.text_widget.insert("1.0", text)
        else:
            # Fallback: create_text_entry stored Entry
            try:
                widget.delete(0, "end")
                widget.insert(0, text)
            except Exception:
                self.item[field_name] = text
    def ai_improve_field(self, field_name):
        try:
            current = self._field_text(field_name)
            context_name = self.item.get("Name") or self.item.get("Title") or self.model_wrapper.entity_type
            # Load templates from config with sensible fallbacks
            default_system = (
                "You are a helpful RPG assistant. Improve the given text for use in a campaign manager adding details and flavor. "
                "Keep it concise, evocative, and suitable for GMs. Return plain text only."
            )
            default_user = "Entity: {context_name}\nField: {field_name}\nText to improve:\n{current}"

            system_tpl = ConfigHelper.get("AI_PROMPTS", "improve_system", fallback=default_system)
            user_tpl = ConfigHelper.get("AI_PROMPTS", "improve_user", fallback=default_user)
            # Allow \n sequences in config to mean newlines
            if isinstance(system_tpl, str):
                system_tpl = system_tpl.replace("\\n", "\n")
            if isinstance(user_tpl, str):
                user_tpl = user_tpl.replace("\\n", "\n")

            # Safe formatting of the user template
            fmt_values = {
                "context_name": context_name,
                "field_name": field_name,
                "current": current,
            }
            try:
                user = user_tpl.format(**fmt_values)
            except Exception:
                user = default_user.format(**fmt_values)
            system = system_tpl
            tone_contract = self._tone_contract_guidance()
            if tone_contract:
                system = f"{system}\n\n{tone_contract}"
            content = execute_ai_chat(
                self._get_ai(),
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                pipeline_name="editor.field_assistance.improve",
                phase="field_improvement",
                phase_message=f"Improving field {field_name}",
            )
            if content:
                self._set_field_text(field_name, content)
        except Exception as e:
            messagebox.showerror("AI Error", f"Failed to improve {field_name}: {e}")
    def ai_draft_field(self, field_name):
        try:
            context_name = self.item.get("Name") or self.item.get("Title") or self.model_wrapper.entity_type
            # Build a lightweight context from common fields if present
            hints = []
            for key in ("NPCs", "Villains", "Places", "Creatures", "Factions", "Objects", "Genre", "Tags", "Objectives"):
                val = self.item.get(key)
                if val:
                    hints.append(f"{key}: {val}")
            joined_hints = "\n".join(hints)
            # Load templates from config with sensible fallbacks
            default_system = (
                "You are a helpful RPG assistant. Draft a compelling field for a campaign item. "
                "Write 1-3 short paragraphs. Return plain text only."
            )
            default_user = (
                "Entity: {context_name}\n"
                "Target field: {field_name}\n"
                "Hints (optional):\n{joined_hints}\n"
                "Draft the field content now."
            )

            system_tpl = ConfigHelper.get("AI_PROMPTS", "draft_system", fallback=default_system)
            user_tpl = ConfigHelper.get("AI_PROMPTS", "draft_user", fallback=default_user)
            # Allow \n sequences in config to mean newlines
            if isinstance(system_tpl, str):
                system_tpl = system_tpl.replace("\\n", "\n")
            if isinstance(user_tpl, str):
                user_tpl = user_tpl.replace("\\n", "\n")

            fmt_values = {
                "context_name": context_name,
                "field_name": field_name,
                "joined_hints": joined_hints,
            }
            try:
                user = user_tpl.format(**fmt_values)
            except Exception:
                user = default_user.format(**fmt_values)
            system = system_tpl
            tone_contract = self._tone_contract_guidance()
            if tone_contract:
                system = f"{system}\n\n{tone_contract}"
            content = execute_ai_chat(
                self._get_ai(),
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                pipeline_name="editor.field_assistance.draft",
                phase="field_drafting",
                phase_message=f"Drafting field {field_name}",
            )
            if content:
                self._set_field_text(field_name, content)
        except Exception as e:
            messagebox.showerror("AI Error", f"Failed to draft {field_name}: {e}")
    def _infer_theme(self, entity_type: str) -> str:
        """Infer a coarse genre/theme string from existing entities of given type."""
        try:
            wrapper = GenericModelWrapper(entity_type)
            items = wrapper.load_items()
        except Exception:
            items = []

        # Preferred explicit fields
        text_fields_priority = ["Genre", "Tags", "Summary", "Description", "Background", "Traits", "Role"]

        corpus = []
        for it in items or []:
            for f in text_fields_priority:
                v = it.get(f)
                if not v:
                    continue
                if isinstance(v, (list, tuple)):
                    corpus.append(" ".join(map(str, v)))
                else:
                    corpus.append(str(v))
        blob = ("\n".join(corpus)).lower()

        # Keyword buckets
        buckets = {
            "medieval fantasy": ["sword", "castle", "knight", "dragon", "elf", "dwarf", "orc", "medieval", "fantasy", "wizard", "mage", "kingdom"],
            "science fiction": ["spaceship", "alien", "planet", "space", "laser", "android", "cyber", "sci-fi", "sci fi", "future", "futuristic", "ai", "robot"],
            "modern": ["modern", "contemporary", "police", "detective", "city", "gun", "phone", "internet", "corporate"],
            "cyberpunk": ["cyberpunk", "neon", "megacorp", "augment", "hacker", "netrunner"],
            "post-apocalyptic": ["post-apocalyptic", "wasteland", "radiation", "zombie", "collapse", "ruins"],
            "horror": ["eldritch", "cthulhu", "haunted", "vampire", "werewolf", "ghost", "horror"],
            "urban fantasy": ["urban fantasy", "occult", "supernatural", "modern magic", "secret society"],
            "steampunk": ["steampunk", "goggles", "airship", "clockwork", "victorian", "steam"],
            "space opera": ["fleet", "galactic", "empire", "hyperspace", "warp", "starship"],
        }

        scores = {k: 0 for k in buckets}
        for theme, kws in buckets.items():
            for kw in kws:
                if kw in blob:
                    scores[theme] += 1

        # Also check for explicit mentions of the theme names
        for theme in list(buckets.keys()):
            if theme in blob:
                scores[theme] += 2

        best = max(scores.items(), key=lambda x: x[1]) if scores else ("", 0)
        if best[1] == 0:
            return "generic"
        return best[0]
