# Open-Brain Memory Skill

Use open-brain as persistent memory for storing and retrieving information across conversations.

## Purpose

Open-brain provides semantic vector search over stored thoughts, notes, and ideas. Use it to:
- Store important information for later retrieval
- Search memories by meaning, not just keywords
- Track tasks, ideas, and references
- Maintain context across sessions

## CLI Commands

### Store Information

```bash
open-brain add "Information to remember"
```

Use this when the user shares important information that should be persisted:
- Preferences, settings, or configuration
- Important facts or decisions
- Tasks or action items
- Ideas or insights
- References to people, projects, or topics

### Search Memories

```bash
open-brain search "query" --limit 10 --threshold 0.3
```

Use this when the user asks about something previously discussed:
- "What did we decide about X?"
- "Do you remember anything about Y?"
- "What tasks are pending?"

### List Recent Memories

```bash
open-brain list --limit 20
open-brain list --type task --days 7
open-brain list --topic python --person "Max"
```

Use this to:
- Get an overview of recent activity
- Filter by type: observation, task, idea, reference, person_note
- Find memories by topic or person
- Limit to recent timeframe

### Get Statistics

```bash
open-brain stats
```

Use this to show memory overview: total count, types, top topics, people.

### Export/Import

```bash
open-brain export backup.json --full
open-brain import backup.json
```

Use for backup and restore operations.

## JSON Output

All commands support `--json` for structured output:

```bash
open-brain search "query" --json
open-brain list --json
open-brain stats --json
```

## Best Practices

### When to Store

Store information when the user:
- Shares a preference or setting
- Makes a decision or agreement
- Assigns a task or action item
- Provides important context
- Mentions a person, project, or topic for future reference

### When to Search

Search memories when the user:
- Asks about previous discussions
- Wants to recall specific information
- Needs context from past conversations
- References something "we discussed before"

### Example Usage Pattern

```bash
# User shares preference
open-brain add "User prefers German language for communication"

# User assigns task
open-brain add "Create unit tests for the authentication module by Friday"

# User mentions important context
open-brain add "Project deadline is March 15th, deployment to production"

# Later, search for context
open-brain search "deadline" --limit 5
open-brain search "authentication tests"

# List pending tasks
open-brain list --type task --days 30
```

## Metadata Extraction

Open-brain automatically extracts:
- **type**: observation, task, idea, reference, person_note
- **topics**: 1-3 short topic tags
- **people**: Mentioned persons
- **action_items**: Implied to-dos
- **dates_mentioned**: Referenced dates

No need to manually categorize - just store the natural text.

## Integration Notes

- The memory persists across sessions in a SQLite database
- Semantic search uses vector embeddings (text-embedding-3-small)
- Rate-limited to avoid API overload
- Supports concurrent access from multiple processes
