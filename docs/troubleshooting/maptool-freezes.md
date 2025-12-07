# MapTool freezing after long sessions

If MapTool becomes unresponsive after several hours of use (busy cursor, UI not updating), the problem is usually inside MapTool itself—our export only generates lightweight token data. The `maptools` exporter builds short `/r` roll macros and optional note comments; it does not launch background threads, deep-copy maps, or ship heavy scripts that could block MapTool's UI thread.

## What the GMCampaignDesigner export actually does
- Creates simple macros that run dice rolls and optional notes, one per action. There are no loops, timers, or file operations that could hang MapTool. 【F:modules/maps/exporters/maptools.py†L10-L43】
- Skips macro generation entirely when an action has neither attack nor damage formulas, and only emits a warning message. That omission cannot freeze MapTool. 【F:modules/maps/exporters/maptools.py†L22-L41】
- If every action is skipped, the exporter logs that no macros were generated; it still outputs a normal token record, so MapTool only loads standard token metadata. 【F:modules/maps/exporters/maptools.py†L36-L43】

## Likely causes inside MapTool
- Long sessions with large images or many tokens can exhaust Java heap memory, leading to UI stalls while the garbage collector runs or the process swaps.
- Autosave or manual save operations on very large campaigns can temporarily block the UI thread.
- Third-party macro packages that fire on token drop or state changes may execute heavy scripts when new tokens are added.

## Mitigations to try
- Reduce asset size before export (portraits, maps, tiles) so MapTool loads less data per token.
- Save, close, and reopen MapTool periodically during marathon sessions to reclaim memory.
- Increase MapTool's Java heap allocation if you routinely load very large maps.
- Temporarily disable or simplify any on-drop/initiative macros from other sources to see if they are the bottleneck.
- Test with a fresh campaign file and a single exported token; if the freeze disappears, gradually add assets until you find the triggering load.

## When to look elsewhere
If MapTool freezes even with a single exported token and no third-party macros, capture a Java thread dump during the hang and share it with the MapTool community. That trace will show whether the stall is in rendering, autosave, or a macro script, and helps confirm that the export data is not responsible.
