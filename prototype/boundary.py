"""The knowledge boundary: keep NPC secrets out of anything she or the player reads.

Narrator prompts may see every NPC's `hidden` secret so characters act consistently.
What the narrator writes back is stored as her memories, diary, and reasons, and is
later shown to protagonist prompts and to the player. Until a secret is revealed,
that text must not carry it. A secret counts as revealed once a fact she knows
shares it, so an unrelated discovery about the same person lifts nothing.

The check is a guard against copied or lightly edited secret text. A paraphrase can
still pass, so it complements the narrator prompt rule and does not replace it.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

# A secret counts as carried when this many consecutive characters of it (ignoring
# punctuation and spacing) appear in the text. Shorter runs flag ordinary talk: the
# tail "不想让任何人知道" of one shipped secret is a common thing to say.
WINDOW = 10
_IGNORED = re.compile(r"[\W_]+")


def normalize(text: str) -> str:
    return _IGNORED.sub("", text).lower()


def shares_secret(text: str, secret: str, window: int = WINDOW) -> bool:
    haystack, needle = normalize(text), normalize(secret)
    if not haystack or not needle:
        return False
    if len(needle) <= window:
        return needle in haystack
    return any(needle[i : i + window] in haystack for i in range(len(needle) - window + 1))


def protected_secrets(
    npcs: Mapping[str, Mapping[str, Any]], known_facts: Iterable[Mapping[str, Any]]
) -> dict[str, str]:
    """The secrets no fact she knows has revealed yet."""
    facts = list(known_facts)
    return {
        npc_id: npc["hidden"]
        for npc_id, npc in npcs.items()
        if npc.get("hidden")
        and not any(f["npc"] == npc_id and shares_secret(f["fact"], npc["hidden"]) for f in facts)
    }


class Screen:
    """Checks text against the secrets she has not been told."""

    def __init__(self, secrets: Mapping[str, str]) -> None:
        self.secrets = dict(secrets)
        self.blocked: list[dict[str, str]] = []

    @classmethod
    def for_state(cls, npcs: Mapping[str, Mapping[str, Any]], state: Mapping[str, Any]) -> Screen:
        return cls(protected_secrets(npcs, state["protagonist"]["known_facts"]))

    @classmethod
    def for_output(
        cls,
        npcs: Mapping[str, Mapping[str, Any]],
        state: Mapping[str, Any],
        discoveries: Iterable[Mapping[str, Any]],
    ) -> tuple[Screen, list[dict[str, Any]]]:
        """A screen for one narrator output, and the discoveries in it that may be kept.

        A discovery about someone may carry only that person's own secret; one that
        carries another person's protected secret is dropped. A kept discovery that
        carries its own person's secret reveals it, so this output may mention it.
        """
        protected = protected_secrets(npcs, state["protagonist"]["known_facts"])
        kept: list[dict[str, Any]] = []
        blocked: list[dict[str, str]] = []
        revealed: set[str] = set()
        for discovery in discoveries:
            other = next(
                (
                    npc_id
                    for npc_id, secret in protected.items()
                    if npc_id != discovery["npc"] and shares_secret(discovery["fact"], secret)
                ),
                None,
            )
            if other is not None:
                blocked.append({"field": "discovery", "npc": other})
                continue
            kept.append(dict(discovery))
            own = npcs.get(discovery["npc"], {}).get("hidden")
            if own and shares_secret(discovery["fact"], own):
                revealed.add(discovery["npc"])
        screen = cls({npc_id: secret for npc_id, secret in protected.items() if npc_id not in revealed})
        screen.blocked = blocked
        return screen, kept

    def leaked(self, text: str | None) -> str | None:
        """The id of an NPC whose protected secret the text carries, if any."""
        if not text:
            return None
        return next((npc_id for npc_id, secret in self.secrets.items() if shares_secret(text, secret)), None)

    def check(self, text: str | None, field: str) -> str | None:
        """Return the text, or None (and record why) if it carries a protected secret."""
        npc_id = self.leaked(text)
        if npc_id is None:
            return text or None
        self.blocked.append({"field": field, "npc": npc_id})
        return None

    def drain(self) -> list[dict[str, str]]:
        """Take the blocked entries recorded so far."""
        taken, self.blocked = self.blocked, []
        return taken
