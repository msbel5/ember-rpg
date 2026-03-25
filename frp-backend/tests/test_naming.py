"""Tests for Module 9: Procedural Naming (FR-39..FR-41)"""
import pytest
from engine.world.naming import NameGenerator, NAME_BANKS


class TestNameGenerator:
    def test_generates_human_name(self):
        gen = NameGenerator(seed=42)
        name = gen.generate_name("human", "male")
        assert isinstance(name, str)
        assert len(name) > 3
        assert " " in name  # first + surname

    def test_generates_dwarf_name(self):
        gen = NameGenerator(seed=42)
        name = gen.generate_name("dwarf", "male")
        assert isinstance(name, str)
        # Dwarf names should use clan names
        assert any(clan in name for clan in NAME_BANKS["dwarf"]["clan_names"])

    def test_generates_elf_name(self):
        gen = NameGenerator(seed=42)
        name = gen.generate_name("elf", "female")
        assert "of the" in name  # Elf house names contain "of the"

    def test_generates_orc_name(self):
        gen = NameGenerator(seed=42)
        name = gen.generate_name("orc", "male")
        assert isinstance(name, str)
        assert len(name) > 3

    def test_uniqueness_no_duplicates(self):
        """AC-26: No two NPCs in same session have identical names."""
        gen = NameGenerator(seed=42)
        names = set()
        for i in range(50):
            name = gen.generate_name("human", "male" if i % 2 == 0 else "female")
            assert name not in names, f"Duplicate name: {name}"
            names.add(name)

    def test_cache_consistency(self):
        """FR-41: Same NPC always gets same name."""
        gen = NameGenerator(seed=42)
        name1 = gen.generate_name("human", "male", npc_id="merchant_1")
        name2 = gen.generate_name("human", "male", npc_id="merchant_1")
        assert name1 == name2

    def test_different_npcs_different_names(self):
        gen = NameGenerator(seed=42)
        name1 = gen.generate_name("human", "male", npc_id="npc_1")
        name2 = gen.generate_name("human", "male", npc_id="npc_2")
        assert name1 != name2

    def test_unknown_faction_falls_back(self):
        gen = NameGenerator(seed=42)
        name = gen.generate_name("goblin", "male")
        assert isinstance(name, str)
        assert len(name) > 3

    def test_female_names_exist(self):
        gen = NameGenerator(seed=42)
        name = gen.generate_name("human", "female")
        assert isinstance(name, str)

    def test_clear_resets_cache(self):
        gen = NameGenerator(seed=42)
        gen.generate_name("human", "male", npc_id="x")
        assert gen.get_cached_name("x") is not None
        gen.clear()
        assert gen.get_cached_name("x") is None
