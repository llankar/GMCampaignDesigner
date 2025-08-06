import json, sqlite3
from modules.helpers.text_helpers import normalize_rtf_json

conn = sqlite3.connect("Dresden Files.db")
c = conn.cursor()

# Assuming Description field is JSON in the 'clues' table:
c.execute("SELECT rowid, Description FROM clues")
rows = c.fetchall()
for rowid, raw in rows:
    desc = json.loads(raw)
    if isinstance(desc, dict) and any(isinstance(r[0], str) for rng in desc.get("formatting",{}).values() for r in rng):
        fixed = normalize_rtf_json(desc)
        c.execute(
          "UPDATE clues SET Description = ? WHERE rowid = ?",
          (json.dumps(fixed), rowid)
        )
conn.commit()
conn.close()
print("Migration complete.")