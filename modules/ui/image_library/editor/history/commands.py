"""Reversible editing commands used by the image editor history stack."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from PIL import Image

from modules.ui.image_library.editor.core.document import ImageDocument
from modules.ui.image_library.editor.core.layer import Layer
from modules.ui.image_library.editor.selection.clipboard import SelectionClipboard


class HistoryCommand(Protocol):
    """Protocol for reversible edit commands."""

    def execute(self) -> None:
        """Apply the command."""

    def undo(self) -> None:
        """Revert the command."""


@dataclass
class LayerState:
    """Serializable copy of a layer."""

    name: str
    visible: bool
    opacity: float
    blend_mode: str
    image: Image.Image


@dataclass
class DocumentState:
    """Serializable snapshot of an entire document."""

    width: int
    height: int
    active_layer_index: int
    layers: list[LayerState]


def snapshot_document(document: ImageDocument) -> DocumentState:
    """Capture a deep copy snapshot of the current document."""
    return DocumentState(
        width=document.width,
        height=document.height,
        active_layer_index=document.active_layer_index,
        layers=[
            LayerState(
                name=layer.name,
                visible=layer.visible,
                opacity=layer.opacity,
                blend_mode=layer.blend_mode,
                image=layer.image.copy(),
            )
            for layer in document.layers
        ],
    )


def apply_document_state(document: ImageDocument, state: DocumentState) -> None:
    """Restore a previously captured document snapshot."""
    document.width = state.width
    document.height = state.height
    document.active_layer_index = state.active_layer_index
    document.layers = [
        Layer(
            name=layer.name,
            visible=layer.visible,
            opacity=layer.opacity,
            blend_mode=layer.blend_mode,
            image=layer.image.copy(),
        )
        for layer in state.layers
    ]


class SnapshotCommand:
    """Command that stores before/after document snapshots."""

    def __init__(self, document: ImageDocument, apply_mutation: Callable[[], None]) -> None:
        self._document = document
        self._apply_mutation = apply_mutation
        self._before = snapshot_document(document)
        self._after: DocumentState | None = None

    def execute(self) -> None:
        if self._after is None:
            self._apply_mutation()
            self._after = snapshot_document(self._document)
            return
        apply_document_state(self._document, self._after)

    def undo(self) -> None:
        apply_document_state(self._document, self._before)


class LayerPatchCommand:
    """Command for painting/erasing by replacing one layer image."""

    def __init__(self, document: ImageDocument, layer_index: int, before: Image.Image, after: Image.Image) -> None:
        self._document = document
        self._layer_index = layer_index
        self._before = before.copy()
        self._after = after.copy()

    def execute(self) -> None:
        self._document.layers[self._layer_index].image = self._after.copy()

    def undo(self) -> None:
        self._document.layers[self._layer_index].image = self._before.copy()


class StrokeCommand(LayerPatchCommand):
    """Reversible paint stroke command."""


class EraseCommand(LayerPatchCommand):
    """Reversible erase stroke command."""


class ClearSelectionCommand(LayerPatchCommand):
    """Reversible command that clears pixels inside a selection mask."""

    def __init__(self, document: ImageDocument, layer_index: int, selection_mask: Image.Image) -> None:
        before = document.layers[layer_index].image.copy()
        after = before.copy()
        transparent = Image.new("RGBA", after.size, (0, 0, 0, 0))
        after.paste(transparent, (0, 0), selection_mask.convert("L"))
        super().__init__(document, layer_index, before, after)


class CutSelectionCommand(LayerPatchCommand):
    """Clear selected pixels and store copied payload in the in-app clipboard."""

    def __init__(
        self,
        document: ImageDocument,
        layer_index: int,
        selection_mask: Image.Image,
        clipboard: SelectionClipboard,
    ) -> None:
        before = document.layers[layer_index].image.copy()
        after = before.copy()
        mask = selection_mask.convert("L")
        bounds = mask.getbbox()
        self._clipboard = clipboard
        self._payload_image: Image.Image | None = None
        self._payload_offset = (0, 0)
        if bounds is not None:
            selected = Image.new("RGBA", before.size, (0, 0, 0, 0))
            selected.paste(before, (0, 0), mask)
            self._payload_image = selected.crop(bounds)
            self._payload_offset = (bounds[0], bounds[1])
        transparent = Image.new("RGBA", after.size, (0, 0, 0, 0))
        after.paste(transparent, (0, 0), mask)
        super().__init__(document, layer_index, before, after)

    def execute(self) -> None:
        super().execute()
        if self._payload_image is not None:
            self._clipboard.set(self._payload_image, self._payload_offset)


class PasteSelectionCommand(LayerPatchCommand):
    """Paste current clipboard payload on the active layer."""

    def __init__(self, document: ImageDocument, layer_index: int, clipboard: SelectionClipboard) -> None:
        payload = clipboard.get()
        before = document.layers[layer_index].image.copy()
        after = before.copy()
        if payload is not None:
            after.alpha_composite(payload.image, payload.offset)
        super().__init__(document, layer_index, before, after)


class RotateCommand(SnapshotCommand):
    """Rotate all layers by a fixed angle."""

    def __init__(self, document: ImageDocument, degrees: int) -> None:
        super().__init__(document, apply_mutation=lambda: document.rotate(degrees))


class FlipCommand(SnapshotCommand):
    """Flip or mirror all layers."""

    def __init__(self, document: ImageDocument, *, horizontal: bool) -> None:
        if horizontal:
            super().__init__(document, apply_mutation=document.mirror)
        else:
            super().__init__(document, apply_mutation=document.flip)


class BrightnessCommand:
    """Reversible command for global brightness factor."""

    def __init__(self, before: float, after: float, setter: Callable[[float], None]) -> None:
        self._before = float(before)
        self._after = float(after)
        self._setter = setter

    def execute(self) -> None:
        self._setter(self._after)

    def undo(self) -> None:
        self._setter(self._before)


class ContrastCommand(BrightnessCommand):
    """Reversible command for global contrast factor."""


class AddLayerCommand(SnapshotCommand):
    """Command that adds a layer."""

    def __init__(self, document: ImageDocument, name: str | None = None) -> None:
        super().__init__(document, apply_mutation=lambda: document.add_layer(name))


class DeleteLayerCommand(SnapshotCommand):
    """Command that deletes the active layer."""

    def __init__(self, document: ImageDocument) -> None:
        super().__init__(document, apply_mutation=document.delete_active_layer)


class MoveLayerCommand(SnapshotCommand):
    """Command that moves the active layer up/down."""

    def __init__(self, document: ImageDocument, direction: int) -> None:
        super().__init__(document, apply_mutation=lambda: document.move_active_layer(direction))


class ToggleLayerVisibilityCommand(SnapshotCommand):
    """Command that toggles active-layer visibility."""

    def __init__(self, document: ImageDocument) -> None:
        super().__init__(document, apply_mutation=lambda: document.toggle_layer_visibility(document.active_layer_index))
