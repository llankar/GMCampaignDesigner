# Random Table JSON Format

Random tables can be provided as a single file (`static/data/random_tables.json`) or as multiple files inside `static/data/random_tables/`. When the folder exists it is preferred, allowing you to break tables out by game system or biome.

Each file uses the same shape:

```json
{
  "system": "Fantasy 5e",          // Optional: system or ruleset the tables belong to
  "biome": "Forest",               // Optional: biome/locale shared by contained tables
  "categories": [
    {
      "id": "encounters",         // Machine-friendly id; falls back to name if omitted
      "name": "Encounters",        // Human friendly label shown in the UI
      "tables": [
        {
          "id": "5e_forest_patrols",    // Unique table id (required)
          "title": "Frontier Patrols",  // Display name (required)
          "dice": "1d12",               // Dice expression to roll (required)
          "description": "Travel complications on the road.",
          "tags": ["forest", "road"],  // Optional tags shown in the panel and filterable
          "entries": [                   // Required; each entry must define a range and a result
            {"range": "1", "result": "A ranger warns about nearby goblins."},
            {"range": "2-3", "result": "A fallen tree blocks the road."}
          ]
        }
      ]
    }
  ]
}
```

### Entries
- `range` can be a single number (e.g., `"4"`) or a range (`"7-9"`).
- Alternatively, you may provide `min` and `max` fields; the loader will convert them into a range automatically.
- `result` is the text shown in the UI and returned by rolls.
- Entry `tags` are optional and surface alongside the result when displayed.

### Validation rules
The loader rejects tables missing **title/name**, **dice**, or **entries**, logging a helpful message. Ranges that cannot be parsed fall back to `1-1` for safety.

### Lookups from code
Use the `RandomTableLoader` helper to read files from either source:

```python
from modules.helpers.random_table_loader import RandomTableLoader

loader = RandomTableLoader()
loaded = loader.load()
print(loader.list_tables())     # returns normalized tables
print(loader.get_table("5e_forest_patrols"))
```

### Shipping samples
The repository includes seed data under `static/data/random_tables/` and a merged fallback at `static/data/random_tables.json`. These cover encounters, inspirations, and environmental events for fantasy forests, dungeons, and orbital stations so GMs can roll immediately.
