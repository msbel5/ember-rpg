# PRD: Character Creation V2 — Immersive Campaign Genesis
**Project:** Ember RPG
**Phase:** 0
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-02
**Status:** Draft
**Supersedes:** Current title_screen.gd creation wizard (STEP_IDENTITY through STEP_SUMMARY)

---

## 1. Purpose

Redesign the character creation flow from a utilitarian form-filling exercise into an immersive, atmospheric experience that makes the player feel like they are discovering their character and world, not filling out a spreadsheet. Reference: Baldur's Gate 1/2 character creation (full-page screens, one decision at a time), Planescape: Torment (atmospheric questions), Dwarf Fortress (world history streaming during generation).

The current creation has these critical UX problems:
- Adapter selection is a dropdown labeled "Fantasy Ember" — meaningless to a new player
- Questionnaire shows all questions at once with dropdowns — not immersive, overwhelming
- Stat rolling shows a flat number array — no visual weight or meaning
- Class/alignment/skills are text inputs — player has to know valid values
- No world history reveal — player doesn't feel the world was created for them
- No loading/generation atmosphere — just waiting

## 2. Scope

### In scope
- 6-step creation flow replacing the current 5-step wizard
- Step 0: Genre Discovery (replaces adapter dropdown)
- Step 1: Identity + Personality Questions (one question per page, all options visible as buttons)
- Step 2: World History Reveal (DF-style streaming text during worldgen)
- Step 3: Stat Rolling (visual dice, body-position stats, pool assignment)
- Step 4: Class, Alignment & Skills (visual cards, axis chart, skill grid)
- Step 5: Dossier & Launch (BG2-style character sheet preview)
- Backend API compatibility: all existing creation endpoints remain, UI changes only
- Keyboard-first: every step completable with keyboard only

### Out of scope
- Backend creation logic changes (API stays the same)
- New character classes or abilities (data-driven, not UX)
- Portrait/avatar art system (future)
- Multiplayer creation

## 3. Functional Requirements (FR)

### Step 0: Commander Identity

**FR-01:** Step 0 presents a name input field and optional advanced settings (world seed, profile). Genre is determined implicitly by the questionnaire answers (adapter weights accumulate from each answer's `adapter_weights` field). The default adapter is `"fantasy_ember"`.

**FR-02:** Advanced settings (world seed, adapter override, profile hint) are hidden behind a "Show Advanced Settings" toggle to keep the default flow clean.

**FR-03:** Keyboard navigation: Tab to cycle fields, Enter to proceed to Step 1.

**FR-04:** The adapter_id ("fantasy_ember" or "scifi_frontier") defaults to "fantasy_ember" and is passed to `Backend.start_campaign_creation()`. Advanced users can override it in the advanced settings panel.

### Step 1: Identity + Personality Questions

**FR-05:** Name input is displayed as a centered, large-text field (24px) with atmospheric prompt text: "What name will they remember?" above it. The field has gold border focus ring. Minimum 2 characters required.

**FR-06:** After name entry, personality questions appear ONE AT A TIME, each on a full page. Each question:
- Large question text at top (22px, centered)
- 4-5 answer options displayed as full-width buttons (NOT dropdown), each showing:
  - Answer title (18px bold)
  - 1-line description (16px muted) explaining what this choice means
- Selected answer: gold highlight + checkmark icon
- Navigation: Up/Down arrows to move focus, Enter to select and auto-advance to next question

**FR-07:** The personality questions are driven by the backend questionnaire API (`creation_payload.questions[]`). Each question group becomes one page. Each question within a group is displayed with all its answers as visible buttons. The UI sends `Backend.answer_campaign_creation()` for each answer.

**FR-08:** Between questions, show brief atmospheric text: "The world listens to your answer..." (0.5s fade, then next question appears). This gives time for backend processing and creates atmosphere.

**FR-09:** Progress indicator at top: "Question 1 of 5" with a simple horizontal progress bar (gold fill).

### Step 2: World History Reveal

**FR-10:** After all questions answered, transition to a full-screen dark panel with streaming text. The backend worldgen results (from `creation_payload.campaign_genesis`) are displayed as DF-style history events appearing one line at a time with 0.3s delay between lines.

**FR-11:** History text format: "Year [N] - [Headline]\n[Summary]\n[Tags]" using data from `campaign_genesis.history_timeline[]`. Each entry has `year`, `headline`, `summary`, `tags[]`, `importance`. The backend generates 30 events spanning ~1200 years. If `history_timeline` is empty, fall back to `history_events[]` string array.

**FR-12:** Text appears with typewriter effect (characters appearing left-to-right at 30 chars/second). Gold text on dark background. Each new line starts with a subtle fade-in.

**FR-13:** A "Continue" button appears at bottom after all text has appeared (or after 8 seconds, whichever is first). Also: pressing Enter or Space at any time skips the animation and shows all text immediately.

**FR-14:** Background: subtle particle drift (reuse existing atmosphere motes from world_view.gd).

### Step 3: Stat Rolling

**FR-15:** Display the rolled stats NOT as a flat array but as a body-position diagram:
```
         [MND: 14]     ← Head (mind)
    [INS: 12]  [PRE: 16]  ← Eyes / Face
         [END: 10]     ← Torso (endurance)
    [MIG: 15]  [AGI: 13]  ← Arms / Legs
```
Each stat shows: abbreviation, value, and modifier in parentheses (e.g., "MIG: 15 (+2)").

**FR-16:** Stat descriptions visible on hover (tooltip or side panel):
- MIG (Might): Raw physical power. Melee damage, carry weight, intimidation.
- AGI (Agility): Speed and reflexes. AC bonus, ranged accuracy, initiative.
- END (Endurance): Stamina and resilience. HP per level, poison resistance, fatigue.
- MND (Mind): Intellect and memory. Spell slots, lore, spell learning chance.
- INS (Insight): Perception and intuition. Will save, trap detection, social read.
- PRE (Presence): Force of personality. CHA checks, leadership, spell DC.

**FR-17:** Three action buttons: "Roll Again" (reroll), "Keep This Roll" (save), "Swap" (exchange current and saved). Roll Again triggers dice animation: 6 dice bounce briefly (0.5s), then reveal new values with a flourish. Keep This Roll: stats pulse gold briefly as confirmation.

**FR-18:** Pool assignment mode: After keeping a roll, the stat values become assignable. The player can click a stat value, then click a position to swap them. Alternatively, +/- buttons on each stat to redistribute within the pool (total must remain constant). "Auto-Assign" button places stats optimally for the recommended class.

**FR-19:** The rolled pool displays: "Roll Pool: [15, 14, 13, 12, 10, 8]" and "Assigned: MIG=15, AGI=13, ..." showing both the pool and current assignment.

### Step 4: Class, Alignment & Skills

**FR-20 (Class Selection):** Display available classes as a grid of cards (3 columns at 1600x900). Each card (minimum 250x180px):
- Class name (20px bold)
- 2-line description (14px)
- Key stats: "Best with: MIG, END" (highlighted if player has high values)
- Hit die: "d10 per level"
- Tag: "Recommended" if stats match class priority (gold badge)
- Click to select: gold border. Click again or click another to switch.

**FR-21 (Alignment Chart):** Display as a 3x3 visual grid:
```
   Lawful Good  |  Neutral Good  |  Chaotic Good
   Lawful Neutral|  True Neutral  |  Chaotic Neutral
   Lawful Evil   |  Chaotic Evil  |  Chaotic Evil
```
Each cell is a clickable button showing alignment name. On hover: 1-line description (e.g., "Lawful Good — Honor, duty, and compassion guide every choice"). Recommended alignment highlighted with gold dot. Selected alignment: gold border + fill.

**FR-22 (Skill Selection):** Display available skills as a scrollable grid of toggle buttons (4 columns). Each skill button:
- Skill name (16px)
- Linked ability (12px muted, e.g., "MIG-based")
- 1-line description on hover tooltip
- Click to toggle on/off
- Budget counter at top: "Skills: 3/5 selected"
- Class-recommended skills have gold dot: "Recommended for Fighter"
- Disabled (grayed) if skill requires a class feature the player doesn't have

**FR-23:** All three selections (class, alignment, skills) are visible simultaneously on the same page in a scrollable layout. Class on left (full height), alignment chart center-top, skills center-bottom.

### Step 5: Dossier & Launch

**FR-24:** Full character sheet preview in BG2-style layout:
- Left column: Character name (24px), class, alignment, portrait placeholder (silhouette)
- Center column: Stat block (6 stats with modifiers, HP, AC, BAB, saves)
- Right column: Skills list, starting equipment (from backend recommendation), special abilities
- Bottom: World premise (2-3 lines from campaign_genesis)

**FR-25:** "Begin Your Story" button: large (400x60px), centered, gold background, white text. On click: 0.5s fade to black, then cinematic text: "You arrive at [settlement_name] with nothing but your wits and a name that means nothing — yet." Then transition to game_session scene.

**FR-26:** "Back" button returns to Step 4 without losing selections. All state preserved across back/forward navigation.

## 4. Data Structures

No new backend data structures. All creation state managed in `title_screen.gd`:

```gdscript
# Existing creation_payload from backend — no changes needed
# New client-side state:
var _genre_selected: String = ""           # "fantasy_ember" | "scifi_frontier"
var _current_question_index: int = 0       # Which question page we're on
var _all_questions_flat: Array = []        # Flattened question list for one-at-a-time display
var _stat_assignment: Dictionary = {}      # {stat_name: assigned_value}
var _selected_class: String = ""
var _selected_alignment: String = ""
var _selected_skills: Array[String] = []
```

## 5. UI Component Specs

### Genre Card (Step 0)
```
PanelContainer (min_size: 400x300)
├── VBoxContainer (alignment: center)
│   ├── Label (genre title, 28px bold)
│   ├── HSeparator
│   └── Label (description, 18px, word_wrap, 3 lines)
```

### Question Page (Step 1)
```
VBoxContainer (anchors: full rect)
├── Label (progress: "Question 1 of 5", 14px muted)
├── ProgressBar (gold fill, 4px height)
├── VSpacer (40px)
├── Label (question text, 22px, centered)
├── VSpacer (30px)
└── VBoxContainer (answers)
    ├── Button (answer 1: title + description, left-aligned, 50px height)
    ├── Button (answer 2: ...)
    ├── Button (answer 3: ...)
    └── Button (answer 4: ...)
```

### Stat Body Diagram (Step 3)
```
CenterContainer
└── Control (custom draw, 400x400)
    ├── Label "MND: 14 (+2)" at (180, 30)   # head
    ├── Label "INS: 12 (+1)" at (80, 100)   # left eye
    ├── Label "PRE: 16 (+3)" at (280, 100)  # right face
    ├── Label "END: 10 (+0)" at (180, 200)  # torso
    ├── Label "MIG: 15 (+2)" at (60, 300)   # left arm
    └── Label "AGI: 13 (+1)" at (300, 300)  # right leg
```

### Class Card (Step 4)
```
PanelContainer (min_size: 250x180)
├── VBoxContainer
│   ├── HBoxContainer
│   │   ├── Label (class name, 20px bold)
│   │   └── Label ("Recommended", gold badge) # if applicable
│   ├── Label (description, 14px, 2 lines)
│   ├── Label ("Best with: MIG, END", 12px muted)
│   └── Label ("Hit die: d10", 12px muted)
```

### Alignment Grid (Step 4)
```
GridContainer (3 columns, 3 rows)
├── Button "Lawful Good" (with tooltip)
├── Button "Neutral Good"
├── ... (9 total)
```

## 6. Acceptance Criteria (AC)

AC-01 [FR-01]: Given title screen, when New Game clicked, then Step 0 shows two genre cards side by side, NOT a dropdown.

AC-02 [FR-02]: Given Step 0, when hovering fantasy card, then card has subtle glow. When clicked, other card fades and transition to Step 1 occurs within 0.3s.

AC-03 [FR-06]: Given Step 1 with 5 questions, then each question appears on its own page with all answers as visible buttons, NOT dropdowns. Only one question visible at a time.

AC-04 [FR-07]: Given a question with 4 answers, all 4 are displayed as full-width buttons with title AND description text visible without clicking.

AC-05 [FR-10]: Given all questions answered, then world history reveal screen shows text appearing one line at a time with typewriter effect.

AC-06 [FR-13]: Given history reveal in progress, when Enter pressed, then all remaining text appears instantly and Continue button activates.

AC-07 [FR-15]: Given Step 3, stats are displayed in body-position layout NOT as a flat array. Each stat shows value and modifier.

AC-08 [FR-17]: Given Roll Again clicked, brief dice animation plays (0.5s), then new values appear.

AC-09 [FR-20]: Given Step 4, classes displayed as grid of cards with name, description, key stats, and "Recommended" tag where applicable. NOT a dropdown.

AC-10 [FR-21]: Given Step 4, alignment displayed as 3x3 visual grid with clickable cells showing alignment name and description on hover. NOT a text input.

AC-11 [FR-22]: Given Step 4, skills displayed as toggleable button grid with budget counter. NOT a text input.

AC-12 [FR-25]: Given Step 5, "Begin Your Story" button triggers fade-to-black with cinematic arrival text before transitioning to gameplay.

AC-13 [FR-03]: Given any step, keyboard-only navigation works: arrows to move focus, Enter to select, Tab to cycle, Escape to go back.

AC-14 [FR-26]: Given Step 4, clicking Back returns to Step 3 with all stat assignments preserved.

## 7. Performance Requirements
- Step transitions: < 0.3s (excluding network calls)
- History reveal typewriter: 30 characters/second, consistent
- Dice roll animation: exactly 0.5s
- Total creation flow: completable in < 3 minutes by experienced player
- All layouts functional at 1600x900 (primary) and 1280x720 (fallback)

## 8. Error Handling
- Backend creation start fails: show error in status label, allow retry
- Question answer fails: show error, keep current answer selected, allow retry
- Empty name: Next button disabled with tooltip "Enter your name"
- No class selected: Next button disabled with tooltip "Choose a class"
- No alignment selected: Next button disabled with tooltip "Choose an alignment"
- Skills over budget: show red counter, disable Next

## 9. Integration Points
- **Backend.gd**: All existing creation endpoints unchanged. start_campaign_creation, answer_campaign_creation, reroll, save-roll, swap-roll, finalize.
- **GameState.gd**: Receives creation_payload updates after each step
- **EmberTheme.gd**: Apply gold accent, dark background, atmospheric styling
- **game_session.tscn**: Transition target after creation finalized

## 10. Test Coverage Target
- Headless Godot test for each step transition
- Keyboard-only navigation test for full flow
- Genre selection both options
- All question types with answer selection
- Stat rolling and pool assignment
- Class/alignment/skill selection
- Back navigation preserving state
- Error states (empty name, missing selections)
- 1600x900 and 1280x720 layout verification
