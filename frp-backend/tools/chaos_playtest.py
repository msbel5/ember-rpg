"""500-turn chaos play-test — finds bugs by exercising every system."""
import sys, os, traceback, json, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.api.game_engine import GameEngine

BUGS = []
TURN_LOG = []

def log_bug(turn, cmd, bug_type, detail):
    entry = {"turn": turn, "cmd": cmd, "type": bug_type, "detail": detail}
    BUGS.append(entry)
    print(f"  ** BUG [{bug_type}] turn {turn}: {detail[:120]}")

def play(engine, session, turn, cmd):
    try:
        r = engine.process_action(session, cmd)
        hp = f"{session.player.hp}/{session.player.max_hp}"
        ap = session.ap_tracker.current_ap if session.ap_tracker else "?"
        combat = "COMBAT" if session.in_combat() else "explore"
        narr = (r.narrative or "")[:150].replace("\n", " ")

        entry = {
            "turn": turn, "cmd": cmd, "combat": combat,
            "hp": hp, "ap": ap, "pos": list(session.position),
            "narrative": narr[:80],
        }
        TURN_LOG.append(entry)

        # Bug detection
        if r.narrative and "traceback" in r.narrative.lower():
            log_bug(turn, cmd, "CRASH_IN_NARRATIVE", narr[:200])
        if r.narrative and "error" in r.narrative.lower() and "narrat" not in r.narrative.lower():
            if "error" not in cmd.lower():
                pass  # some errors are valid game responses
        if session.player.hp < 0:
            log_bug(turn, cmd, "NEGATIVE_HP", f"HP={session.player.hp}")
        if session.ap_tracker and session.ap_tracker.current_ap < 0:
            log_bug(turn, cmd, "NEGATIVE_AP", f"AP={session.ap_tracker.current_ap}")
        if session.ap_tracker and session.ap_tracker.current_ap > session.ap_tracker.max_ap:
            log_bug(turn, cmd, "AP_OVERFLOW", f"AP={session.ap_tracker.current_ap}/{session.ap_tracker.max_ap}")

        return r
    except Exception as e:
        tb = traceback.format_exc()
        log_bug(turn, cmd, "EXCEPTION", f"{type(e).__name__}: {e}\n{tb[-300:]}")
        return None

def run_chaos():
    engine = GameEngine()

    # Phase 1: Create session, verify spawn
    print("=== PHASE 1: SPAWN & EXPLORE (turns 1-50) ===")
    s = engine.new_session("Chaos", "rogue", location="Harbor Town")

    # Check spawn is walkable
    px, py = s.position
    walkable_neighbors = 0
    for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
        if s.map_data and s.map_data.is_walkable(px+dx, py+dy):
            blocked = s.spatial_index.blocking_at(px+dx, py+dy) if s.spatial_index else False
            if not blocked:
                walkable_neighbors += 1
    if walkable_neighbors < 1:
        log_bug(0, "spawn", "SPAWN_TRAPPED", f"pos={s.position} walkable_neighbors={walkable_neighbors}")

    turn = 0

    # Explore
    explore_cmds = [
        "look around",
        "move south", "move south", "move east",
        "look around",
        "move north", "move west", "move west",
        "look around",
        "move south", "move east", "move east", "move east",
        "look around",
    ]
    for cmd in explore_cmds:
        turn += 1
        play(engine, s, turn, cmd)

    # Find and approach every NPC
    npc_names = []
    for eid, ent in s.entities.items():
        name = ent.get("name", "")
        role = ent.get("role", "")
        if role and name:
            npc_names.append((name, role))

    for name, role in npc_names[:6]:  # approach up to 6 NPCs
        turn += 1
        r = play(engine, s, turn, f"approach {name}")
        if r and "too far" in (r.narrative or "").lower():
            log_bug(turn, f"approach {name}", "APPROACH_FAIL", f"Still too far after approach")

        turn += 1
        r = play(engine, s, turn, f"talk to {name}")
        if r and "too far" in (r.narrative or "").lower():
            log_bug(turn, f"talk to {name}", "TALK_AFTER_APPROACH_FAIL", f"Too far after approach")

        turn += 1
        play(engine, s, turn, "move south")  # move away

    # Fill remaining phase 1 turns
    while turn < 50:
        turn += 1
        cmd = random.choice(["move north", "move south", "move east", "move west", "look around"])
        play(engine, s, turn, cmd)

    # Phase 2: Social interactions
    print("\n=== PHASE 2: SOCIAL (turns 51-120) ===")
    social_cmds = [
        "approach merchant",
        "talk to merchant",
        "think what do I know about this town's history",
        "think what do I know about magic",
        "think what do I know about the gods",
        "persuade merchant give me a discount",
        "intimidate merchant",
        "deceive merchant I am the mayors envoy",
        "bribe merchant 10 gold",
        "move south",
        "approach guard",
        "talk to guard",
        "persuade guard let me pass",
        "intimidate guard",
        "bribe guard 5 gold",
        "move north",
        "approach blacksmith",
        "talk to blacksmith",
        "persuade blacksmith teach me",
        "move south",
    ]
    for cmd in social_cmds:
        turn += 1
        play(engine, s, turn, cmd)

    while turn < 120:
        turn += 1
        cmd = random.choice([
            "look around", "examine area",
            "move north", "move south", "move east", "move west",
            "think what happened here", "think about nature",
        ])
        play(engine, s, turn, cmd)

    # Phase 3: Crime spree
    print("\n=== PHASE 3: CRIME SPREE (turns 121-200) ===")
    crime_cmds = [
        "approach merchant",
        "steal from merchant",
        "sneak",
        "steal from merchant",
        "attack merchant",
        "attack", "attack", "attack",
        "flee",
        "short rest",
        "look around",
        "approach guard",
        "attack guard",
        "attack", "attack",
        "disengage",
        "flee",
        "short rest",
        "long rest",
    ]
    for cmd in crime_cmds:
        turn += 1
        r = play(engine, s, turn, cmd)
        if r is None:
            break  # exception occurred

    while turn < 200:
        turn += 1
        if s.in_combat():
            cmd = random.choice(["attack", "attack", "flee", "disengage"])
        else:
            cmd = random.choice(["move north", "move south", "move east", "move west", "look around", "short rest"])
        play(engine, s, turn, cmd)

    # Phase 4: Recovery and quests
    print("\n=== PHASE 4: RECOVERY & QUESTS (turns 201-300) ===")
    recovery_cmds = [
        "long rest",
        "look around",
        "inventory",
        "approach merchant",
        "talk to merchant",
    ]
    for cmd in recovery_cmds:
        turn += 1
        play(engine, s, turn, cmd)

    # Check for quest offers and try to accept
    if hasattr(s, 'quest_offers') and s.quest_offers:
        for offer in s.quest_offers[:2]:
            title = offer.get("title", "unknown")
            turn += 1
            play(engine, s, turn, f"accept quest {title}")

    quest_cmds = [
        "look around", "move north", "move north", "move east",
        "look around", "examine area",
        "move south", "move south", "move west",
        "craft bread", "craft",
        "inventory",
        "equip iron sword",
        "unequip weapon",
        "equip daggers",
        "drop bread",
        "pick up bread",
        "use bread",
        "fill waterskin",
    ]
    for cmd in quest_cmds:
        turn += 1
        play(engine, s, turn, cmd)

    while turn < 300:
        turn += 1
        if s.in_combat():
            cmd = random.choice(["attack", "flee"])
        else:
            cmd = random.choice([
                "move north", "move south", "move east", "move west",
                "look around", "examine area", "search",
                "short rest", "inventory",
            ])
        play(engine, s, turn, cmd)

    # Phase 5: Save/Load verification
    print("\n=== PHASE 5: SAVE/LOAD (turns 301-350) ===")

    # Capture state before save
    pre_save_hp = s.player.hp
    pre_save_pos = list(s.position)
    pre_save_inv_count = len(s.inventory) if hasattr(s, 'inventory') else 0

    turn += 1
    play(engine, s, turn, "save game chaostest")
    turn += 1
    play(engine, s, turn, "move south")
    turn += 1
    play(engine, s, turn, "move south")
    turn += 1
    r = play(engine, s, turn, "load game chaostest")

    # Verify state restored
    if s.player.hp != pre_save_hp:
        log_bug(turn, "load verification", "SAVE_LOAD_HP_MISMATCH", f"expected={pre_save_hp} got={s.player.hp}")
    if list(s.position) != pre_save_pos:
        log_bug(turn, "load verification", "SAVE_LOAD_POS_MISMATCH", f"expected={pre_save_pos} got={list(s.position)}")

    while turn < 350:
        turn += 1
        if s.in_combat():
            cmd = random.choice(["attack", "flee"])
        else:
            cmd = random.choice(["move north", "move south", "look around", "inventory"])
        play(engine, s, turn, cmd)

    # Phase 6: Endurance (turns 351-500)
    print("\n=== PHASE 6: ENDURANCE (turns 351-500) ===")
    all_cmds = [
        "move north", "move south", "move east", "move west",
        "look around", "examine area", "search",
        "inventory", "short rest",
        "approach merchant", "talk to merchant",
        "think about history", "think about magic",
        "sneak", "hide",
        "attack", "flee",
        "craft", "use bread",
        "pray",
    ]

    while turn < 500:
        turn += 1
        if s.in_combat():
            cmd = random.choice(["attack", "attack", "attack", "flee", "disengage"])
        else:
            cmd = random.choice(all_cmds)
        play(engine, s, turn, cmd)

    # Final report
    print("\n" + "=" * 60)
    print(f"CHAOS PLAY-TEST COMPLETE: {turn} turns")
    print(f"BUGS FOUND: {len(BUGS)}")
    print("=" * 60)

    if BUGS:
        # Group by type
        by_type = {}
        for b in BUGS:
            t = b["type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(b)

        for btype, items in sorted(by_type.items()):
            print(f"\n  [{btype}] x{len(items)}")
            for item in items[:3]:  # show first 3 of each type
                print(f"    turn {item['turn']}: {item['cmd']} -> {item['detail'][:100]}")
            if len(items) > 3:
                print(f"    ... and {len(items)-3} more")
    else:
        print("\n  NO BUGS FOUND! Game is clean.")

    # Save bug report
    report = {
        "total_turns": turn,
        "total_bugs": len(BUGS),
        "bugs": BUGS,
        "bug_summary": {t: len(items) for t, items in by_type.items()} if BUGS else {},
    }
    with open("chaos_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nFull report saved to chaos_report.json")

if __name__ == "__main__":
    random.seed(42)  # deterministic for reproducibility
    run_chaos()
