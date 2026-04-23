# Release Notes

## Unreleased
- Added a brief "Please wait" indicator and wait cursor while importing or exporting JSON so that users know the app is working before the file dialog closes. The cursor and modal dismiss automatically when the operation finishes or fails.
- Internal cleanup in GM Table workspace/map panel routing removed duplicated adjacent logic and added focused regression tests (_screen_to_world conversion, snap preview invalidation, and map tool focus fallback behavior). No user-facing feature changes.
- Documented the application documentation workflow, including how to refresh committed docs with `scripts/generate_docs.py`.
