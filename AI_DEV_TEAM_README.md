# AI Dev Team Feature Lab

## Overview
The `ai_dev_team/` folder introduces an autonomous feature pipeline that can inspect the repository, propose one useful feature, evaluate risk/value, plan implementation, apply scoped changes, run tests, and prepare git metadata for PR workflows.

## Architecture
- `repo_analyzer.py`: scans repository structure (Python/tests/UI/docs).
- `context_builder.py`: builds compact context for agents.
- `feature_agent.py`: generates one feature proposal centered on usability/automation/UI.
- `feature_score.py`: approves/rejects proposals using guardrails.
- `planner_agent.py`: creates ordered implementation steps.
- `coder_agent.py`: applies small, auditable changes.
- `test_agent.py`: executes `pytest` and reports status.
- `pr_agent.py`: creates branch + commit, optionally pushes.
- `feature_lab.py`: orchestrates full pipeline.
- `prompts/*.txt`: reusable prompt templates for LLM-backed agent variants.

## End-to-end workflow
1. Generate feature proposal.
2. Score and reject risky/useless features.
3. Build implementation plan.
4. Implement changes.
5. Run tests (`pytest`).
6. Create git branch and commit (`--commit`), and optionally push (`--push`).

## Run locally
From repository root:

```bash
python ai_dev_team/feature_lab.py
```

Optional git actions:

```bash
python ai_dev_team/feature_lab.py --commit
python ai_dev_team/feature_lab.py --push
```

## Scheduling
### Cron (Linux/macOS)
Run every day at 02:30:

```cron
30 2 * * * cd /path/to/GMCampaignDesigner && /usr/bin/python3 ai_dev_team/feature_lab.py --commit >> logs/feature_lab.log 2>&1
```

### Windows Task Scheduler
1. Open **Task Scheduler** → **Create Task**.
2. Trigger: daily (or desired cadence).
3. Action: **Start a program**.
   - Program/script: `python`
   - Add arguments: `ai_dev_team/feature_lab.py --commit`
   - Start in: `C:\path\to\GMCampaignDesigner`
4. Enable run history/logging (redirect output with a `.bat` wrapper if needed).

## Notes
- The current coder agent is intentionally conservative and writes execution artifacts under `ai_dev_team/last_run/`.
- Replace agent internals with provider-specific LLM calls if deeper automation is required.
