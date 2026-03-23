# PRD: Per-NPC Persistent Memory
# Phase 3b — Key Differentiator (Mantella-inspired)
# Priority: CRITICAL — Players' #1 request across all AI RPGs

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
