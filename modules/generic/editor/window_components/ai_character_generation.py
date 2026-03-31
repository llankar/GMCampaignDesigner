"""Utilities for window components AI character generation."""

from modules.generic.editor.window_context import *


class GenericEditorWindowAICharacterGeneration:
    def ai_generate_full_npc(self):
        """Handle AI generate full NPC."""
        try:
            # Keep AI generate full NPC resilient if this step fails.
            theme = self._infer_theme("npcs")
            # Gather sample names/roles
            try:
                samples = GenericModelWrapper("npcs").load_items()
            except Exception:
                samples = []
            examples = []
            for it in samples[:8]:
                # Process each it from samples[:8].
                n = it.get("Name")
                r = it.get("Role") or it.get("Traits")
                if n:
                    examples.append(f"- {n}{' ('+r+')' if r else ''}")
            examples_text = "\n".join(examples)

            system = (
                "You are an RPG NPC generator. Produce concise, game-usable material. "
                "Return ONLY compact JSON without code fences."
            )
            user = (
                f"Theme: {theme}\n"
                f"Existing NPCs (optional):\n{examples_text}\n\n"
                "Task: Generate an NPC object with fields:\n"
                "{\n"
                "  \"Name\": string,\n"
                "  \"Role\": string,\n"
                "  \"Description\": string (1 short paragraph, Markdown allowed),\n"
                "  \"Secret\": string,\n"
                "  \"Quote\": string,\n"
                "  \"RoleplayingCues\": string,\n"
                "  \"Personality\": string,\n"
                "  \"Motivation\": string,\n"
                "  \"Background\": string,\n"
                "  \"Traits\": string,\n"
                "  \"Genre\": string\n"
                "}\n"
                "Constraints: No extra keys. No code blocks. Keep within ~400 words."
            )
            # Build prompt and call AI
            content = run_ai_editor_chat(
                self._get_ai(),
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                pipeline_name="editor.character_generation.npc",
                feature="character_generation",
                entity_type="npcs",
                action_label="Generate NPC",
                phase="npc_generation",
                phase_message="Generating NPC content",
            )
            try:
                data = LocalAIClient._parse_json_safe(content)
            except Exception:
                data = {"Name": "Generated NPC", "Description": content, "Genre": theme}

            # Apply simple text fields
            for key in ("Name", "Role", "Quote", "Genre"):
                # Process each key from ('Name', 'Role', 'Quote', 'Genre').
                val = data.get(key)
                if val:
                    self._set_field_text(key, str(val))

            # Apply longtext fields
            for key in ("Description", "Secret", "RoleplayingCues", "Personality", "Motivation", "Background", "Traits"):
                # Process each key while updating AI generate full NPC.
                val = data.get(key)
                if val:
                    self._set_field_text(key, str(val))

        except Exception as e:
            messagebox.showerror("AI Error", f"Failed to generate NPC: {e}")
    def ai_generate_full_creature(self):
        """Handle AI generate full creature."""
        try:
            # Prefer explicit Genre from existing creatures; fallback to inferred theme
            try:
                existing = GenericModelWrapper("creatures").load_items() or []
            except Exception:
                existing = []

            genre_counts = {}
            for it in existing:
                # Process each it from existing.
                g = (it.get("Genre") or "").strip()
                if not g:
                    continue
                genre_counts[g] = genre_counts.get(g, 0) + 1

            if genre_counts:
                # Pick the most common explicit Genre
                theme = max(genre_counts.items(), key=lambda kv: kv[1])[0]
            else:
                theme = self._infer_theme("creatures")

            # Gather sample names/types for context
            samples = existing
            examples = []
            for it in samples[:8]:
                # Process each it from samples[:8].
                n = it.get("Name")
                t = it.get("Type")
                if n:
                    examples.append(f"- {n}{' ('+t+')' if t else ''}")
            examples_text = "\n".join(examples)

            # Extract representative Stats examples to enforce format consistency
            stats_examples = []
            for it in existing:
                # Process each it from existing.
                s = it.get("Stats")
                if not s:
                    continue
                if isinstance(s, dict):
                    s = s.get("text", "")
                s = str(s).strip()
                if not s:
                    continue
                if 20 <= len(s) <= 1200:
                    stats_examples.append(s)
                if len(stats_examples) >= 3:
                    break
            stats_examples_text = "\n\n---\n\n".join(stats_examples) if stats_examples else ""
            stats_block = (
                f"Stats Format Examples (match structure and labels):\n---\n{stats_examples_text}\n---\n\n"
                if stats_examples_text else ""
            )

            system = (
                "You are an RPG creature/monster generator. Produce concise, game-usable material. "
                "Return ONLY compact JSON without code fences."
            )
            user = (
                f"Theme/Genre: {theme}\n"
                f"Existing Creatures (optional):\n{examples_text}\n\n"
                f"{stats_block}"
                "Task: Generate a Creature object with fields:\n"
                "{\n"
                "  \"Name\": string,\n"
                "  \"Type\": string,\n"
                "  \"Description\": string (1 short paragraph, Markdown allowed),\n"
                "  \"Weakness\": string,\n"
                "  \"Powers\": string,\n"
                "  \"Stats\": string (follow the above template),\n"
                "  \"Background\": string,\n"
                "  \"Genre\": string\n"
                "}\n"
                "Constraints: No extra keys. No code blocks. Keep within ~300-400 words."
            )
            # Build prompt and call AI
            content = run_ai_editor_chat(
                self._get_ai(),
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                pipeline_name="editor.character_generation.creature",
                feature="character_generation",
                entity_type="creatures",
                action_label="Generate Creature",
                phase="creature_generation",
                phase_message="Generating creature content",
            )
            try:
                data = LocalAIClient._parse_json_safe(content)
            except Exception:
                data = {"Name": "Generated Creature", "Description": content, "Genre": theme}

            # Ensure Genre coherence if model omitted it
            if not data.get("Genre"):
                data["Genre"] = theme

            # Apply simple text fields
            for key in ("Name", "Type", "Genre"):
                # Process each key from ('Name', 'Type', 'Genre').
                val = data.get(key)
                if val:
                    self._set_field_text(key, str(val))

            # Apply longtext fields
            for key in ("Description", "Weakness", "Powers", "Stats", "Background"):
                # Process each key while updating AI generate full creature.
                val = data.get(key)
                if val:
                    self._set_field_text(key, str(val))

        except Exception as e:
            messagebox.showerror("AI Error", f"Failed to generate Creature: {e}")
