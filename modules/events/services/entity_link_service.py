from modules.generic.generic_model_wrapper import GenericModelWrapper


class EntityLinkService:
    """Load/search linkable entities for calendar events."""

    SUPPORTED_TYPES = ("Places", "NPCs", "Scenarios", "Informations")

    def __init__(self, wrappers=None):
        self._wrappers = wrappers if isinstance(wrappers, dict) else {}
        self._entities_cache = {}

    def list_entities(self, entity_type, force_refresh=False):
        if not force_refresh and entity_type in self._entities_cache:
            return list(self._entities_cache[entity_type])

        wrapper = self._resolve_wrapper(entity_type)
        if wrapper is None:
            return []

        key_field = self._key_field(entity_type)
        entities = []
        for item in wrapper.load_items():
            value = item.get(key_field)
            if isinstance(value, str) and value.strip():
                entities.append(value.strip())

        values = sorted(set(entities), key=str.lower)
        self._entities_cache[entity_type] = tuple(values)
        return list(values)

    def search_entities(self, entity_type, query):
        values = self.list_entities(entity_type)
        text = str(query or "").strip().lower()
        if not text:
            return values
        return [name for name in values if text in name.lower()]

    def invalidate_cache(self, entity_type=None):
        if entity_type:
            self._entities_cache.pop(entity_type, None)
            return
        self._entities_cache.clear()

    def _resolve_wrapper(self, entity_type):
        slug = self._slug_for(entity_type)
        if not slug:
            return None

        wrapper = self._wrappers.get(slug)
        if wrapper is None:
            wrapper = GenericModelWrapper(slug)
            self._wrappers[slug] = wrapper
        return wrapper

    @staticmethod
    def _slug_for(entity_type):
        mapping = {
            "Places": "places",
            "NPCs": "npcs",
            "Scenarios": "scenarios",
            "Informations": "informations",
        }
        return mapping.get(entity_type)

    @staticmethod
    def _key_field(entity_type):
        if entity_type in ("Scenarios", "Informations"):
            return "Title"
        return "Name"
