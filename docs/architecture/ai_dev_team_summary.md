# AI Dev Team Architecture Summary Command

The feature lab now supports a lightweight architecture snapshot mode:

```bash
python -m ai_dev_team.feature_lab --workspace . --architecture-summary
```

Example output:

```text
Repository: /workspace/GMCampaignDesigner
Python files: 1342
Test files: 50
UI files: 58
Docs files: 8
Top modules: venvDS, modules, tests, ai_dev_team, scripts, db, auto-tests, campaign_generator.py
```

Implementation notes:
- CLI-specific logic is isolated in `ai_dev_team/cli/architecture_summary.py`.
- Repository inspection remains centralized in `ai_dev_team/repo_analyzer.py`.
