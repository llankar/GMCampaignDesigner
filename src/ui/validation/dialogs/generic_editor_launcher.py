"""Launch helpers for creating validation targets with the Generic Editor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol

from src.validation import ValidationIssue
from src.validation.reference_validator import ReferenceRecord

TemplateLoader = Callable[[str], Mapping[str, Any]]
WrapperFactory = Callable[[str], Any]


class EditorFactory(Protocol):
    """Factory contract for ``GenericEditorWindow`` compatible editors."""

    def __call__(
        self,
        master: Any,
        item: dict[str, Any],
        template: Mapping[str, Any],
        wrapper: Any,
        *,
        creation_mode: bool = False,
    ) -> Any:
        """Create an editor window."""


class PersistableWrapper(Protocol):
    """Persistence contract used by the Generic Editor launcher."""

    entity_type: str

    def save_item(self, item: dict[str, Any], **kwargs: Any) -> None:
        """Persist one item."""


@dataclass(frozen=True)
class GenericEditorCreationRequest:
    """Context required to open a pre-filled creation editor."""

    expected_type: str
    referenced_name: str
    parent_identifier: str = ""
    parent_type: str = ""
    source_identifier: str = ""
    source_type: str = ""
    extra_values: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenericEditorCreationResult:
    """Entity returned by the Generic Editor after a successful save."""

    entity: dict[str, Any]
    entity_slug: str


class GenericEditorLauncher:
    """Open the app Generic Editor for validation-driven entity creation.

    Dependencies are injectable so validation dialogs stay easy to unit-test and
    the heavyweight CustomTkinter editor is imported only when a real UI action
    needs it.
    """

    def __init__(
        self,
        *,
        editor_factory: EditorFactory | None = None,
        template_loader: TemplateLoader | None = None,
        wrapper_factory: WrapperFactory | None = None,
        wait_for_editor: bool = True,
    ) -> None:
        self._editor_factory = editor_factory
        self._template_loader = template_loader
        self._wrapper_factory = wrapper_factory
        self._wait_for_editor = wait_for_editor

    def create_entity(
        self,
        master: Any,
        request: GenericEditorCreationRequest,
    ) -> GenericEditorCreationResult | None:
        """Open the Generic Editor and return the saved entity, if any."""

        entity_slug = entity_slug_for_expected_type(request.expected_type)
        template = self._load_template(entity_slug)
        wrapper = self._create_wrapper(entity_slug)
        item = build_prefilled_entity(template, request)
        editor = self._create_editor(master, item, template, wrapper)

        if self._wait_for_editor:
            _wait_window(master, editor)

        if not getattr(editor, "saved", False):
            return None

        saved_entity = getattr(editor, "item", item)
        if not isinstance(saved_entity, dict):
            saved_entity = item
        wrapper.save_item(saved_entity)
        return GenericEditorCreationResult(entity=saved_entity, entity_slug=entity_slug)

    def _load_template(self, entity_slug: str) -> Mapping[str, Any]:
        if self._template_loader is not None:
            return self._template_loader(entity_slug)

        from modules.helpers.template_loader import load_template

        return load_template(entity_slug)

    def _create_wrapper(self, entity_slug: str) -> PersistableWrapper:
        if self._wrapper_factory is not None:
            return self._wrapper_factory(entity_slug)

        from modules.generic.generic_model_wrapper import GenericModelWrapper

        return GenericModelWrapper(entity_slug)

    def _create_editor(
        self,
        master: Any,
        item: dict[str, Any],
        template: Mapping[str, Any],
        wrapper: PersistableWrapper,
    ) -> Any:
        if self._editor_factory is not None:
            return self._editor_factory(master, item, template, wrapper, creation_mode=True)

        from modules.generic.generic_editor_window import GenericEditorWindow

        return GenericEditorWindow(master, item, template, wrapper, creation_mode=True)


_ENTITY_SLUG_OVERRIDES = {
    "npc": "npcs",
    "pc": "pcs",
    "scenario": "scenarios",
    "location": "places",
    "place": "places",
    "object": "objects",
    "information": "informations",
    "info": "informations",
    "clue": "clues",
    "faction": "factions",
    "creature": "creatures",
    "villain": "villains",
    "map": "maps",
    "book": "books",
    "event": "events",
    "campaign": "campaigns",
}
_NAME_FIELD_CANDIDATES = ("Name", "Title", "name", "title", "Label", "label")
_PARENT_FIELD_CANDIDATES = (
    "Parent",
    "ParentId",
    "Parent ID",
    "ParentIdentifier",
    "parent",
    "parent_id",
    "parent_identifier",
)
_TYPE_FIELD_CANDIDATES = ("type", "entity_type", "Type", "EntityType")


def creation_request_from_issue(
    issue: ValidationIssue,
    reference: ReferenceRecord | None = None,
) -> GenericEditorCreationRequest:
    """Build a Generic Editor creation request from a missing-reference issue."""

    payload = issue.payload
    parent_identifier = ""
    parent_type = ""
    source_identifier = payload.source_entity
    source_type = payload.source_type

    if reference is not None:
        parent_identifier = reference.source.identifier
        parent_type = reference.source.entity_type
        source_identifier = reference.source.identifier or source_identifier
        source_type = reference.source.entity_type or source_type

    if not parent_identifier:
        parent_identifier = source_identifier
    if not parent_type:
        parent_type = source_type

    return GenericEditorCreationRequest(
        expected_type=payload.expected_type,
        referenced_name=payload.referenced_name,
        parent_identifier=parent_identifier,
        parent_type=parent_type,
        source_identifier=source_identifier,
        source_type=source_type,
    )


def entity_slug_for_expected_type(expected_type: str) -> str:
    """Return the Generic Editor entity slug for a validator expected type."""

    normalized = str(expected_type or "").strip().lower().replace(" ", "_")
    if not normalized:
        raise ValueError("expected_type is required")
    if normalized in _ENTITY_SLUG_OVERRIDES:
        return _ENTITY_SLUG_OVERRIDES[normalized]
    if normalized.endswith("s"):
        return normalized
    if normalized.endswith("y"):
        return f"{normalized[:-1]}ies"
    return f"{normalized}s"


def build_prefilled_entity(
    template: Mapping[str, Any],
    request: GenericEditorCreationRequest,
) -> dict[str, Any]:
    """Create the item passed to Generic Editor with name and parent pre-filled."""

    field_names = _template_field_names(template)
    entity: dict[str, Any] = dict(request.extra_values)
    name_field = _first_existing(field_names, _NAME_FIELD_CANDIDATES) or "Name"
    entity.setdefault(name_field, request.referenced_name)

    type_field = _first_existing(field_names, _TYPE_FIELD_CANDIDATES)
    if type_field:
        entity.setdefault(type_field, request.expected_type)

    parent_field = _first_existing(field_names, _PARENT_FIELD_CANDIDATES)
    if parent_field and request.parent_identifier:
        entity.setdefault(parent_field, request.parent_identifier)

    if request.parent_identifier:
        entity.setdefault("__validation_parent", request.parent_identifier)
    if request.parent_type:
        entity.setdefault("__validation_parent_type", request.parent_type)
    if request.source_identifier:
        entity.setdefault("__validation_source", request.source_identifier)
    if request.source_type:
        entity.setdefault("__validation_source_type", request.source_type)
    entity.setdefault("__validation_expected_type", request.expected_type)
    return entity


def _template_field_names(template: Mapping[str, Any]) -> tuple[str, ...]:
    fields = template.get("fields", ())
    names: list[str] = []
    if not isinstance(fields, (list, tuple)):
        return ()
    for field in fields:
        if isinstance(field, Mapping):
            name = str(field.get("name", "")).strip()
            if name:
                names.append(name)
    return tuple(names)


def _first_existing(field_names: tuple[str, ...], candidates: tuple[str, ...]) -> str:
    existing = set(field_names)
    return next((candidate for candidate in candidates if candidate in existing), "")


def _wait_window(master: Any, editor: Any) -> None:
    wait_owner = master if hasattr(master, "wait_window") else editor
    wait = getattr(wait_owner, "wait_window", None)
    if callable(wait):
        wait(editor)
