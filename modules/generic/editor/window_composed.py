from modules.generic.editor.window_base import GenericEditorWindowBase
from modules.generic.editor.window_components import (
    GenericEditorWindowNavigationAndRendering,
    GenericEditorWindowSceneFields,
    GenericEditorWindowListAndBasicFields,
    GenericEditorWindowRandomContentGeneration,
    GenericEditorWindowFormActionsAndPersistence,
    GenericEditorWindowPortraitAndImageWorkflows,
    GenericEditorWindowAssetPathAndPreview,
    GenericEditorWindowAIFieldAssistance,
    GenericEditorWindowAIScenarioGeneration,
    GenericEditorWindowAICharacterGeneration,
)


class GenericEditorWindow(
    GenericEditorWindowBase,
    GenericEditorWindowNavigationAndRendering,
    GenericEditorWindowSceneFields,
    GenericEditorWindowListAndBasicFields,
    GenericEditorWindowRandomContentGeneration,
    GenericEditorWindowFormActionsAndPersistence,
    GenericEditorWindowPortraitAndImageWorkflows,
    GenericEditorWindowAssetPathAndPreview,
    GenericEditorWindowAIFieldAssistance,
    GenericEditorWindowAIScenarioGeneration,
    GenericEditorWindowAICharacterGeneration,
):
    pass
