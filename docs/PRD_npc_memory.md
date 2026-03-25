# PRD: Per-NPC Persistent Memory
**Project:** Ember RPG  
**Phase:** 3  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-23  
**Status:** Draft

## 1. Overview
Every NPC maintains a persistent memory file. When the player interacts with an NPC, their memory is loaded into the LLM context. NPCs remember past conversations, reference previous events, and change behavior over time.

## 2. Why This Matters
- AI Dungeon: NPCs forget everything after context window
- BG3: NPCs remember via scripted flags, not dynamic memory
- Skyrim Mantella: Proved this works — players say it "transforms the game"
- Our approach: Structured memory + LLM = best of both worlds

## 3. Memory Architecture

### Per-NPC Memory File (JSON)
```python
class NPCMemory:
    npc_id: str
    name: str

    # Relationship
    relationship_score: int = 0  # -100 to +100
    relationship_label: str = "stranger"  # stranger/acquaintance/friend/ally/enemy

    # Conversation History (summarized, not raw)
    conversations: list[ConversationSummary] = []
    # [{date, summary, sentiment, key_topics}]
    # MAX 10 summaries — oldest get merged into long_term_memory

    # Key Facts the NPC Knows About Player
    known_facts: list[str] = []
    # ["Player killed the bandit leader", "Player is a mage", "Player lied about the treasure"]

    # NPC's Current Emotional State
    emotional_state: str = "neutral"  # neutral/happy/angry/afraid/suspicious/grateful

    # What NPC Wants from Player (if anything)
    current_desire: str = ""  # "wants player to find lost ring"

    # Long-term Memory (compressed from old conversations)
    long_term_memory: str = ""
    # "Player helped me twice. Trustworthy. Mage. Killed bandits. Curious about the old ruins."

    # Last interaction timestamp
    last_interaction: str = ""
```

### Conversation Summarization
After each NPC interaction, summarize and store:

```python
def summarize_conversation(npc_memory, raw_conversation):
    summary = ConversationSummary(
        date=current_game_time,
        summary=llm_summarize(raw_conversation, max_tokens=50),
        sentiment=detect_sentiment(raw_conversation),  # positive/negative/neutral
        key_topics=extract_topics(raw_conversation)  # ["quest", "payment", "threat"]
    )
    npc_memory.conversations.append(summary)

    # Merge old conversations if > 10
    if len(npc_memory.conversations) > 10:
        oldest = npc_memory.conversations.pop(0)
        npc_memory.long_term_memory += f" {oldest.summary}"

    # Update relationship
    if summary.sentiment == "positive":
        npc_memory.relationship_score += 5
    elif summary.sentiment == "negative":
        npc_memory.relationship_score -= 5

    # Update label
    npc_memory.relationship_label = score_to_label(npc_memory.relationship_score)
```

## 4. LLM Context Injection
When player talks to NPC, build context:

```python
def build_npc_context(npc_memory, npc_template, world_state):
    return f"""You are {npc_memory.name}, a {npc_template.role} in {npc_template.location}.

Personality: {npc_template.personality}
Current mood: {npc_memory.emotional_state}

Your relationship with the player:
- Status: {npc_memory.relationship_label} (score: {npc_memory.relationship_score})
- You know: {', '.join(npc_memory.known_facts)}
- Long-term impression: {npc_memory.long_term_memory}

Recent conversations:
{format_recent_conversations(npc_memory.conversations[-3:])}

Current desire: {npc_memory.current_desire}

World context:
{build_world_context_for_npc(world_state, npc_memory.npc_id)}

Stay in character. Reference past interactions naturally. Do not break character."""
```

## 5. Memory-Driven Behaviors

| Memory State | NPC Behavior |
|-------------|-------------|
| First meeting | Introduces self, generic dialogue |
| relationship > 30 | Offers discounts, shares rumors |
| relationship > 60 | Offers personal quest, calls player by name |
| relationship < -20 | Short answers, refuses optional help |
| relationship < -50 | Refuses all interaction |
| knows_fact("killed_merchant") | References it: "I heard what you did to old Tom..." |
| emotional_state = "afraid" | Nervous dialogue, offers to pay for safety |
| emotional_state = "grateful" | Gives bonus items, warns of danger |

## 6. NPC-to-NPC Gossip (Tier 3)
NPCs share information about the player:
```python
def gossip_propagate(source_npc, target_npc, fact):
    # NPCs in same location share facts
    if source_npc.location == target_npc.location:
        if fact not in target_npc.known_facts:
            target_npc.known_facts.append(f"Heard from {source_npc.name}: {fact}")
```

## 7. Acceptance Criteria

### AC-1: Memory Persistence
- [ ] NPC memories survive save/load
- [ ] Memories survive game session restart
- [ ] Each NPC has independent memory

### AC-2: Conversation Summarization
- [ ] After each conversation, a summary is generated
- [ ] Old summaries merge into long_term_memory
- [ ] Max 10 recent summaries per NPC

### AC-3: Relationship Tracking
- [ ] Positive interactions increase score
- [ ] Negative interactions decrease score
- [ ] Score affects NPC behavior (dialogue, prices, quest availability)

### AC-4: Fact Tracking
- [ ] Key player actions are recorded as NPC facts
- [ ] NPCs reference facts in dialogue
- [ ] Facts propagate via gossip (same location)

### AC-5: LLM Context
- [ ] NPC memory injected into every LLM call
- [ ] Context includes relationship, facts, emotional state
- [ ] Recent conversations included (last 3)

### AC-6: API Endpoints
- [ ] GET /game/session/{id}/npc/{npc_id}/memory
- [ ] NPC memory included in save/load
- [ ] Memory updates after every interaction

## 8. Test Scenarios
1. Talk to NPC twice → second time references first conversation
2. Help NPC → relationship increases, dialogue changes
3. Kill NPC's friend → NPC becomes hostile, references the death
4. Save/load → NPC memory preserved
5. 15 conversations → old ones merged into long_term_memory
6. Two NPCs in same location → gossip propagation works

---

## Header
**Project:** Ember RPG
**Phase:** 3b
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-03-23
**Status:** Draft

---

## 9. Functional Requirements

**FR-01:** Each NPC must have an independent `NPCMemory` instance identified by `npc_id`.

**FR-02:** After each interaction, `summarize_conversation()` must generate a `ConversationSummary` and append it to `npc_memory.conversations`.

**FR-03:** When `len(conversations) > 10`, the oldest entry must be merged into `long_term_memory` and removed from `conversations`.

**FR-04:** `relationship_score` must increase by 5 on positive sentiment and decrease by 5 on negative sentiment, clamped to [-100, 100].

**FR-05:** `relationship_label` must be computed from `relationship_score` using fixed thresholds: ≤-50 = enemy, ≤-20 = hostile, ≤30 = stranger, ≤60 = acquaintance, else friend/ally.

**FR-06:** `build_npc_context()` must include NPC name, role, personality, emotional_state, relationship_score, relationship_label, known_facts, long_term_memory, and last 3 conversation summaries.

**FR-07:** A fact added via `known_facts.append()` must appear in all subsequent LLM context strings for that NPC.

**FR-08:** NPCs in the same location must propagate facts via `gossip_propagate()` — the receiving NPC's `known_facts` must contain the fact prefixed with `"Heard from {source.name}: "`.

**FR-09:** `GET /game/session/{id}/npc/{npc_id}/memory` must return the full `NPCMemory` for the specified NPC.

**FR-10:** NPC memories must be included in session save/load (survive restart).

---

## 10. Data Structures

```python
@dataclass
class ConversationSummary:
    date: str              # Game time string
    summary: str           # LLM-generated, max 50 tokens
    sentiment: str         # "positive" | "negative" | "neutral"
    key_topics: List[str]  # e.g. ["quest", "payment"]

@dataclass
class NPCMemory:
    npc_id: str
    name: str
    relationship_score: int = 0       # -100 to +100
    relationship_label: str = "stranger"
    conversations: List[ConversationSummary] = field(default_factory=list)
    known_facts: List[str] = field(default_factory=list)
    emotional_state: str = "neutral"
    current_desire: str = ""
    long_term_memory: str = ""
    last_interaction: str = ""
```

---

## 11. Public API

```python
def summarize_conversation(npc_memory: NPCMemory, raw_conversation: str) -> None:
    """Generates ConversationSummary, appends to npc_memory.conversations.
    If len > 10, merges oldest into long_term_memory. Updates relationship_score and label."""

def build_npc_context(npc_memory: NPCMemory, npc_template, world_state) -> str:
    """Returns formatted string for LLM system prompt injection."""

def gossip_propagate(source_npc: NPCMemory, target_npc: NPCMemory, fact: str) -> None:
    """If fact not already in target.known_facts, appends 'Heard from {source.name}: {fact}'."""
```

---

## 12. Acceptance Criteria (Standard Format)

AC-01 [FR-01]: Given two NPCs with different npc_ids, when each has a conversation, then their `known_facts` and `relationship_score` are independent.

AC-02 [FR-02]: Given an NPC with 0 conversations, when `summarize_conversation()` is called, then `len(npc_memory.conversations) == 1` with a valid summary.

AC-03 [FR-03]: Given an NPC with 10 conversations, when `summarize_conversation()` is called again, then `len(conversations) == 10` and `long_term_memory` contains text from the oldest summary.

AC-04 [FR-04]: Given an NPC with `relationship_score=0`, when two positive interactions occur, then `relationship_score == 10`. When a negative interaction occurs, then `relationship_score == 5`.

AC-05 [FR-06]: Given a built NPC context string, when inspected, then it contains the NPC's name, relationship_label, and at least the last conversation summary.

AC-06 [FR-08]: Given NPC A (source) and NPC B (target) in the same location, when `gossip_propagate(A, B, "Player killed Tom")` is called, then B's `known_facts` contains `"Heard from A.name: Player killed Tom"`.

AC-07 [FR-10]: Given a session with NPC memories, when the session is saved and reloaded, then all NPC memories are preserved with identical relationship_scores and known_facts.

---

## 13. Performance Requirements

- `summarize_conversation()` (LLM call excluded): < 5ms
- `build_npc_context()`: < 2ms
- `gossip_propagate()`: < 1ms
- Memory serialization for 50 NPCs: < 10ms

---

## 14. Error Handling

| Condition | Behavior |
|---|---|
| LLM unavailable for summarization | Use truncated raw_conversation as fallback summary |
| `relationship_score` out of bounds | Clamped to [-100, 100] |
| Duplicate fact in `known_facts` | `gossip_propagate()` skips if already present |
| NPC memory not found | `GET /npc/{id}/memory` returns 404 |

---

## 15. Integration Points

- **World State (Phase 3a):** NPC disposition updates flow through world_state.npc_states
- **Consequence System (Phase 3c):** Social consequence effects call `adjust_disposition()` on NPCMemory
- **DM Agent (Module 6):** `build_npc_context()` injected into NPC dialogue LLM calls
- **Save/Load:** NPCMemory dict serialized per session
- **API Layer:** `GET /game/session/{id}/npc/{npc_id}/memory` endpoint

---

## 16. Test Coverage Target

- **Target:** ≥ 90% line coverage
- **Must cover:** conversation trim at 10+, relationship label thresholds, gossip duplicate prevention, context build output format, save/load round-trip
