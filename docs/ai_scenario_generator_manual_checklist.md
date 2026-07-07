# AI Scenario Generator Manual Test Checklist

Use this checklist after UI changes to the scenario generator.

- Create a prompt in **Manage Prompts**.
- Edit the prompt name, prompt text, category, description, and questions.
- Duplicate a prompt and confirm duplicate-name validation can be resolved by renaming.
- Delete a prompt and confirm the confirmation dialog appears.
- Export prompts to JSON, then import them back.
- Restore default prompts and verify **Professional RPG Scenario** is available.
- Generate a scenario with Ollama unavailable and verify a clear provider-unavailable error is shown.
- Generate a scenario with Ollama running and verify the UI stays responsive while loading.
- Edit the AI-generated result preview.
- Save the edited scenario to the DB and verify duplicate titles are blocked.
- Export the AI-generated scenario to DOCX.
- Switch back to random generator mode and verify legacy generation, saving, and DOCX export still work.
