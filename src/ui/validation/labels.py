"""English default labels and messages for validation UI surfaces."""

VALIDATION_TITLE = "Validation"
VALIDATION_SUMMARY_TITLE = "Validation summary"
VALIDATION_SUMMARY_MESSAGE = "Hierarchy consistency check completed."
VALIDATION_CAMPAIGN_TITLE = "Campaign validation"

CORRECTED_LABEL = "Corrected"
IGNORED_LABEL = "Ignored"
REMAINING_LABEL = "Remaining"
ENTITIES_VISITED_LABEL = "Entities visited"
REFERENCES_CHECKED_LABEL = "References checked"
ELAPSED_TIME_LABEL = "Elapsed time"
CLOSE_LABEL = "Close"

NO_ENTITIES_FOUND_MESSAGE = "No entities found under selected campaign."
CAMPAIGN_DATA_UNAVAILABLE_TITLE = "Campaign data unavailable"
CAMPAIGN_DATA_UNAVAILABLE_MESSAGE = (
    "The data store or entity services could not be found. "
    "Open or reload a campaign project before running validation again."
)
CAMPAIGN_REQUIRED_TITLE = "Campaign required"
CAMPAIGN_REQUIRED_MESSAGE = (
    "No campaign was selected for validation. "
    "Select an active campaign, then run validation again."
)
VALIDATION_UNAVAILABLE_TITLE = "Validation unavailable"
VALIDATION_UNAVAILABLE_MESSAGE = (
    "Validation could not start because of an initialization error. "
    "Verify that the project is loaded, then run validation again."
)
TECHNICAL_DETAIL_LABEL = "Technical detail"
VALIDATION_IMPOSSIBLE_TITLE = "Validation unavailable"
HIERARCHY_CONSISTENCY_TITLE = "Hierarchy consistency"
IGNORE_ISSUE_PROMPT = (
    "Ignore this issue for this session and continue validation?\n\n"
    "Choose Yes to ignore it now. Choose No to open resolution options."
)
INVALID_HIERARCHY_RESOLUTION_TITLE = "Resolve hierarchy issue"
INVALID_HIERARCHY_RESOLUTION_MESSAGE = (
    "Choose how to handle this hierarchy problem. You can remove the invalid "
    "reference, ignore the issue for this session, or stop validation."
)
INVALID_HIERARCHY_ATTACH_RESOLUTION_MESSAGE = (
    "Choose how to handle this hierarchy problem. You can attach the existing "
    "target under the source, remove the invalid reference, ignore the issue "
    "for this session, or stop validation."
)
INVALID_HIERARCHY_REMAP_RESOLUTION_MESSAGE = (
    "Choose how to handle this hierarchy problem. You can remap the reference "
    "to another target, remove the invalid reference, ignore the issue for "
    "this session, or stop validation."
)
INVALID_HIERARCHY_ATTACH_REMAP_RESOLUTION_MESSAGE = (
    "Choose how to handle this hierarchy problem. You can attach the existing "
    "target under the source, remap the reference to another target, remove "
    "the invalid reference, ignore the issue for this session, or stop validation."
)
STOP_VALIDATION_LABEL = "Stop validation"
NO_HIERARCHY_REMAP_TARGET_SELECTOR_MESSAGE = (
    "No hierarchy target selector is configured for remapping."
)

AMBIGUOUS_REFERENCE_TITLE = "Ambiguous reference"
AMBIGUOUS_REFERENCE_MESSAGE = (
    "\u201c{referenced_name}\u201d matches multiple {expected_type} entities. "
    "Choose the target to remap."
)
CHOOSE_LEFT_LABEL = "Choose left"
CHOOSE_RIGHT_LABEL = "Choose right"
VIEW_OTHER_CANDIDATES_LABEL = "View other candidates"
IGNORE_LABEL = "Ignore"
CANDIDATE_UNAVAILABLE_MESSAGE = "Candidate unavailable for this ambiguous reference."
NO_OTHER_CANDIDATE_SELECTOR_MESSAGE = "No other-candidate selector is configured."
NO_KEY_INFO_MESSAGE = "No key info available."
TYPE_LABEL = "Type"
PATH_LABEL = "Path"
TAGS_LABEL = "Tags"

MISSING_REFERENCE_TITLE = "Missing reference"
MISSING_REFERENCE_MESSAGE = (
    "\u201c{referenced_name}\u201d is expected as {expected_type} from {source_entity}."
)
CREATE_LABEL = "Create"
ATTACH_LABEL = "Attach"
REMAP_LABEL = "Remap"
REMOVE_LABEL = "Remove"
NO_REMAP_TARGET_SELECTOR_MESSAGE = "No target selector is configured for remapping."
REMAPPING_UNAVAILABLE_TITLE = "Remapping unavailable"
CHOOSE_REMAP_TARGET_TITLE = "Choose remap target"
CHOOSE_REMAP_TARGET_MESSAGE = (
    "Select an existing compatible entity to replace this missing reference."
)
NO_REMAP_TARGETS_MESSAGE = "No compatible existing entities are available for remapping."
REMAP_TARGET_SEARCH_LABEL = "Search targets"
REMAP_TARGET_SEARCH_PLACEHOLDER = "Type a name, id, or path..."
NO_REMAP_TARGET_SEARCH_RESULTS_MESSAGE = "No targets match your search."

CHOOSE_CAMPAIGN_TITLE = "Choose a campaign"
CHOOSE_CAMPAIGN_MESSAGE = (
    "Select the campaign to check. Validation will start only after this choice."
)
NO_CAMPAIGNS_MESSAGE = (
    "No campaigns exist yet. Create or import a campaign before running validation."
)
CANCEL_LABEL = "Cancel"
RUN_LABEL = "Run"

ENTITY_CREATION_PENDING_MESSAGE = (
    "Entity creation is pending: link the created entity or cancel."
)
ISSUE_IGNORED_MESSAGE = "Issue ignored for this session: {referenced_name}"
ENTITY_CREATION_REQUESTED_MESSAGE = (
    "Entity creation requested. Validation will resume after saving."
)
REFERENCE_NOT_FOUND_ACTION_MESSAGE = (
    "Cannot apply action: validation reference not found."
)
RESUME_NO_ENTITY_MESSAGE = "Cannot resume: no created entity was provided."
REFERENCE_NOT_FOUND_RESUME_MESSAGE = (
    "Cannot resume: validation reference not found."
)
VALIDATION_CANCELED_MESSAGE = "Validation canceled by the GM."
VALIDATION_COMPLETED_MESSAGE = "Validation completed."
UNKNOWN_ACTION_MESSAGE = "Unknown action: {action}"
ISSUE_REFERENCE_MESSAGE = (
    "{issue_type}: {source_entity}.{field} references "
    "\u201c{referenced_name}\u201d ({expected_type})."
)
