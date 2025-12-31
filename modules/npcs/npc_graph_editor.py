from modules.characters.character_graph_editor import CharacterGraphEditor
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


class NPCGraphEditor(CharacterGraphEditor):
    def __init__(self, master, npc_wrapper, faction_wrapper, *args, **kwargs):
        pc_wrapper = GenericModelWrapper("pcs")
        super().__init__(
            master,
            npc_wrapper=npc_wrapper,
            pc_wrapper=pc_wrapper,
            faction_wrapper=faction_wrapper,
            allowed_entity_types={"npc"},
            *args,
            **kwargs,
        )
