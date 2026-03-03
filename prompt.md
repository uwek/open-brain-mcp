# Aufgabe

wir bauen einen mcp-server und eine begleitende cli-anwendung, die informationen speichern und auf anfrage als kontext zur verfügung stellen soll. der mcp-server soll im produktionsbetrieb per http erreichbar sein.

# Tech-stack

- python, fastmcp, sqlite, sqlite-vec
- llms für metadata-extraction und embeddings via openrouter.ai
- alle dateien zu diesem projekt in `./open-brain/` anlegen

führe für den zugraiff auf sqlite-vec eine Umgebungsvariable ein und beschreibe in README.md genau, wie sqlite-vec auf macos und linux zu installieren ist.

# Datenbank

das datenbank-setup ist hier in postgres-sql angegeben. bitte in sqlite-sql umsetzen:

```sql
-- Create the thoughts table
create table thoughts (
  id uuid default gen_random_uuid() primary key,
  content text not null,
  embedding vector(1536),
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Index for fast vector similarity search
create index on thoughts
  using hnsw (embedding vector_cosine_ops);

-- Index for filtering by metadata fields
create index on thoughts using gin (metadata);

-- Index for date range queries
create index on thoughts (created_at desc);

-- Auto-update the updated_at timestamp
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger thoughts_updated_at
  before update on thoughts
  for each row
  execute function update_updated_at();
```

die datenbank wird beim programmstart automatsch erstellt, wenn sie noch nicht existiert.

# mcp-server funktionen

## add(thought)

aus einem neuen thought werden für thoughts.metadata mittels `openai/gpt-4o-mini` metadaten extrahiert. dazu dient der folgende prompt:

```
Extract metadata from the user's captured thought. Return JSON with:
- "people": array of people mentioned (empty if none)
- "action_items": array of implied to-dos (empty if none)
- "dates_mentioned": array of dates YYYY-MM-DD (empty if none)
- "topics": array of 1-3 short topic tags (always at least one)
- "type": one of "observation", "task", "idea", "reference", "person_note"
Only extract what's explicitly there.
```

dann wird mittels `openai/text-embedding-3-small` für thoughts.embedding aus thought ein embedding-vector erzeugt und der datensatz gespeichert.

## search(text)

description: "Search captured thoughts by meaning. Use this when the user asks about a topic, person, or idea they've previously captured."

## list()

description: "List recently captured thoughts with optional filters by type, topic, person, or time range."

## stats()

description: "Get a summary of all captured thoughts: totals, types, top topics, and people."

# cli-anwendung

die oben beschriebenen mcp-server-funktionen sollen auch durch eine cli-anwendung zugänglich sein:

```
openbrain [add|list|stats|search] "text"
```

die cli-anwendung soll wahlweise markdown oder json ausgeben. ich bevorzuge .md

