"""The knowledge boundary: what counts as a leaked secret and what gets blocked."""

from __future__ import annotations

from prototype import boundary

SECRET = "放学后偷偷在校外奶茶店打工，帮家里还债，不想让任何人知道。"
OTHER = "其实很欣赏林夏的文字，担心自己会输给她。"
THIRD = "暑假听到林夏随口说她“太黏人”，一直很受伤。"
NPCS = {
    "zhou_yu": {"hidden": SECRET},
    "shen_zhiyi": {"hidden": OTHER},
    "xu_nian": {"hidden": THIRD},
}


def state(*facts):
    return {"protagonist": {"known_facts": [{"npc": npc, "fact": fact} for npc, fact in facts]}}


def test_a_verbatim_or_lightly_edited_copy_of_the_secret_is_a_leak() -> None:
    assert boundary.shares_secret(SECRET, SECRET)
    assert boundary.shares_secret("他说：放学后，偷偷在校外奶茶店打工！", SECRET)
    assert boundary.shares_secret("PS " + SECRET.replace("，", " "), SECRET)
    assert boundary.shares_secret(SECRET.replace("偷偷", "悄悄"), SECRET)


def test_the_window_is_exactly_ten_characters() -> None:
    assert boundary.WINDOW == 10
    assert boundary.shares_secret(SECRET[:10], SECRET)
    assert not boundary.shares_secret(SECRET[:9], SECRET)
    assert boundary.shares_secret("……" + SECRET[-12:], SECRET)  # the last window counts too (10 characters)


def test_punctuation_spacing_and_case_do_not_hide_a_copy() -> None:
    assert boundary.shares_secret("放学后，偷偷，在校外，奶茶店，打工", SECRET)
    assert boundary.shares_secret("  放 学 后 偷 偷 在 校 外 奶 茶 店 ", SECRET)
    assert boundary.shares_secret("ABC secret code 123456789".upper(), "abc secret code 123456789")


def test_ordinary_talk_that_echoes_a_phrase_of_a_secret_is_not_a_leak() -> None:
    for sentence in (
        "我不想让任何人知道爸妈在闹离婚。",
        "其实我也不想让任何人知道这件事",
        "我担心自己会输给她",
        "周屿今天上课又打瞌睡了，放学后一个人走了。",
    ):
        assert not any(boundary.shares_secret(sentence, s["hidden"]) for s in NPCS.values()), sentence
    assert not boundary.shares_secret("", SECRET)
    assert not boundary.shares_secret("anything", "")


def test_short_secrets_must_match_whole() -> None:
    assert boundary.shares_secret("他怕黑。", "怕黑")
    assert not boundary.shares_secret("他不怕。", "怕黑")


def test_a_secret_is_revealed_only_by_a_fact_that_carries_it() -> None:
    assert set(boundary.protected_secrets(NPCS, [])) == set(NPCS)
    unrelated = state(("zhou_yu", "周屿今天忘了带伞，借了她的。"))
    assert set(boundary.Screen.for_state(NPCS, unrelated).secrets) == set(NPCS)
    revealed = state(("zhou_yu", SECRET))
    assert set(boundary.Screen.for_state(NPCS, revealed).secrets) == {"shen_zhiyi", "xu_nian"}
    # a fact filed under someone else does not reveal this person's secret
    misfiled = state(("xu_nian", SECRET))
    assert "zhou_yu" in boundary.Screen.for_state(NPCS, misfiled).secrets


def test_a_blocked_field_is_recorded_once_and_can_be_drained() -> None:
    screen = boundary.Screen.for_state(NPCS, state())

    assert screen.check("今天很平常。", "memory") == "今天很平常。"
    assert screen.check(f"听说{SECRET}", "memory") is None
    assert screen.check(None, "focus") is None
    assert screen.drain() == [{"field": "memory", "npc": "zhou_yu"}]
    assert screen.drain() == []


def test_a_discovery_may_carry_its_own_secret_and_then_the_output_may_mention_it() -> None:
    screen, kept = boundary.Screen.for_output(NPCS, state(), [{"npc": "zhou_yu", "fact": SECRET}])

    assert [d["npc"] for d in kept] == ["zhou_yu"]
    assert screen.check(f"我终于知道了：{SECRET}", "memory") is not None
    assert screen.check(f"她说：{OTHER}", "memory") is None  # other secrets stay protected
    assert screen.drain() == [{"field": "memory", "npc": "shen_zhiyi"}]


def test_a_discovery_carrying_another_persons_secret_is_dropped_and_unlocks_nothing() -> None:
    screen, kept = boundary.Screen.for_output(NPCS, state(), [{"npc": "xu_nian", "fact": SECRET}])

    assert kept == []
    assert screen.drain() == [{"field": "discovery", "npc": "zhou_yu"}]
    assert "xu_nian" in screen.secrets and "zhou_yu" in screen.secrets
    assert screen.check(f"我听见：{THIRD}", "memory") is None


def test_chained_discoveries_cannot_launder_a_secret() -> None:
    screen, kept = boundary.Screen.for_output(
        NPCS,
        state(),
        [{"npc": "zhou_yu", "fact": OTHER}, {"npc": "shen_zhiyi", "fact": THIRD}],
    )

    assert kept == []
    assert {entry["npc"] for entry in screen.blocked} == {"shen_zhiyi", "xu_nian"}


def test_an_unrelated_discovery_keeps_the_secret_protected() -> None:
    screen, kept = boundary.Screen.for_output(
        NPCS, state(), [{"npc": "zhou_yu", "fact": "周屿今天忘了带伞，借了她的。"}]
    )

    assert len(kept) == 1
    assert screen.check(f"我总觉得：{SECRET}", "memory") is None
