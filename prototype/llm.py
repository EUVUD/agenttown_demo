"""Model providers for the prototype: Anthropic, OpenAI-compatible, and an offline fake.

Real providers only use the standard library, so the prototype runs without the
locked environment. API keys come from environment variables and are never logged.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"
DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"

VALIDATION_ERRORS = (ValueError, KeyError, TypeError, AttributeError)


class LLMError(RuntimeError):
    """The provider could not be reached or rejected the request."""


class InvalidModelOutput(ValueError):
    """The model output was still invalid after one repair attempt."""


@dataclass(frozen=True)
class LLMRequest:
    task: str
    system: str
    prompt: str
    # Structured facts for the offline fake; never sent to a real provider.
    context: Mapping[str, Any] = field(default_factory=dict)
    max_tokens: int = 1500


class Provider:
    name = "base"
    model = ""

    @property
    def label(self) -> str:
        return f"{self.name}:{self.model}" if self.model else self.name

    def complete(self, request: LLMRequest) -> str:
        raise NotImplementedError


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(
        self, api_key: str, model: str, base_url: str = DEFAULT_ANTHROPIC_BASE_URL
    ) -> None:
        self._api_key = api_key
        self.model = model
        self._base_url = base_url.rstrip("/")

    def complete(self, request: LLMRequest) -> str:
        data = _post_json(
            f"{self._base_url}/v1/messages",
            {
                "model": self.model,
                "max_tokens": request.max_tokens,
                "system": request.system,
                "messages": [{"role": "user", "content": request.prompt}],
            },
            {"x-api-key": self._api_key, "anthropic-version": "2023-06-01"},
        )
        return "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )


class OpenAICompatibleProvider(Provider):
    name = "openai"

    def __init__(
        self, api_key: str, model: str, base_url: str = DEFAULT_OPENAI_BASE_URL
    ) -> None:
        self._api_key = api_key
        self.model = model
        self._base_url = base_url.rstrip("/")

    def complete(self, request: LLMRequest) -> str:
        data = _post_json(
            f"{self._base_url}/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": request.prompt},
                ],
            },
            {"authorization": f"Bearer {self._api_key}"},
        )
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise LLMError("unexpected response shape from the provider") from None


def _setting(env: Mapping[str, str], name: str) -> str | None:
    """Read MARGINALIA_<name>, falling back to the project's old AGENTTOWN_<name>."""
    return env.get(f"MARGINALIA_{name}") or env.get(f"AGENTTOWN_{name}")


def provider_from_env(
    choice: str | None = None, env: Mapping[str, str] | None = None
) -> Provider:
    """Pick a provider from MARGINALIA_LLM (auto|anthropic|openai|fake) and keys.

    The old AGENTTOWN_LLM and AGENTTOWN_MODEL names are still read when the new
    ones are unset.
    """
    env = os.environ if env is None else env
    choice = (choice or _setting(env, "LLM") or "auto").strip().lower()
    if choice == "auto":
        if env.get("ANTHROPIC_API_KEY"):
            choice = "anthropic"
        elif env.get("OPENAI_API_KEY"):
            choice = "openai"
        else:
            choice = "fake"
    if choice == "anthropic":
        key = env.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("MARGINALIA_LLM=anthropic needs ANTHROPIC_API_KEY")
        return AnthropicProvider(
            key,
            _setting(env, "MODEL") or DEFAULT_ANTHROPIC_MODEL,
            env.get("ANTHROPIC_BASE_URL") or DEFAULT_ANTHROPIC_BASE_URL,
        )
    if choice == "openai":
        key, model = env.get("OPENAI_API_KEY"), _setting(env, "MODEL")
        if not key or not model:
            raise LLMError("MARGINALIA_LLM=openai needs OPENAI_API_KEY and MARGINALIA_MODEL")
        return OpenAICompatibleProvider(
            key, model, env.get("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL
        )
    if choice == "fake":
        return FakeProvider()
    raise LLMError(f"unknown MARGINALIA_LLM value: {choice!r}")


def _post_json(
    url: str, body: Mapping[str, Any], headers: Mapping[str, str], timeout: float = 180
) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"content-type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise LLMError(f"provider returned HTTP {exc.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LLMError(f"provider unreachable: {exc}") from None
    except json.JSONDecodeError:
        raise LLMError("provider returned a non-JSON response") from None


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)

REPAIR_PROMPT = """你上一次的输出不符合要求：{error}

原始要求（节选）：
{original}

你的输出：
{raw}

请只输出修正后的 JSON 对象，不要任何其他文字。"""


def extract_json(text: str) -> dict:
    candidates = [match.group(1) for match in _FENCE.finditer(text)] + [text]
    for candidate in candidates:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start == -1 or end <= start:
            continue
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("no JSON object found in model output")


def complete_json(
    provider: Provider,
    request: LLMRequest,
    validate: Callable[[dict], dict],
    *,
    salvage: Callable[[str], dict | None] | None = None,
) -> tuple[dict, dict]:
    """Return (validated output, meta), repairing invalid output at most once.

    `salvage` may turn a non-JSON answer into a valid result without a repair
    call. Raises InvalidModelOutput if the repair is still invalid and LLMError
    if the provider itself fails.
    """
    raw = provider.complete(request)
    try:
        return validate(extract_json(raw)), {"repaired": False}
    except VALIDATION_ERRORS as exc:
        first_error = str(exc)
    if salvage is not None:
        salvaged = salvage(raw)
        if salvaged is not None:
            return salvaged, {"salvaged": True, "error": first_error}
    repair = LLMRequest(
        task="repair",
        system=request.system,
        prompt=REPAIR_PROMPT.format(
            error=first_error, original=request.prompt[-2500:], raw=raw[:3000]
        ),
        context={**request.context, "task": request.task},
        max_tokens=request.max_tokens,
    )
    raw = provider.complete(repair)
    try:
        return validate(extract_json(raw)), {"repaired": True, "error": first_error}
    except VALIDATION_ERRORS as exc:
        raise InvalidModelOutput(f"{first_error}; after repair: {exc}") from None


class FakeProvider(Provider):
    """Deterministic offline stand-in that returns plausible structured output."""

    name = "fake"
    model = "offline"

    def complete(self, request: LLMRequest) -> str:
        task = request.context.get("task", request.task) if request.task == "repair" else request.task
        handler = getattr(self, f"_fake_{task}", None)
        if handler is None:
            raise LLMError(f"fake provider has no script for task {task!r}")
        seed = hashlib.sha256(f"{task}\n{request.prompt}".encode("utf-8")).hexdigest()
        return json.dumps(handler(request.context, random.Random(seed)), ensure_ascii=False)

    def _fake_chat(self, ctx: Mapping[str, Any], rng: random.Random) -> dict:
        text = str(ctx.get("text", ""))
        target = next((npc for npc in ctx.get("npcs", []) if npc["name"] in text), None)
        if any(word in text for word in _SUGGESTION_WORDS):
            who = target["name"] if target else "这件事"
            return {
                "reply": rng.choice(
                    [
                        f"……你是说{who}？我想想。说实话有点怕，但你说得也不是没道理。",
                        f"嗯……{who}啊。我不保证会照做，不过我会认真想想的。",
                        "你总是比我直接。好吧，看情况。",
                    ]
                ),
                "influence": {"text": text[:40], "target": target["id"] if target else None},
                "mood": rng.choice(["有点犹豫", "被推了一把", "心里有数了"]),
            }
        if any(mark in text for mark in ("?", "？", "吗", "怎么")):
            place = ctx.get("location_name", "学校")
            return {
                "reply": rng.choice(
                    [
                        f"怎么说呢……今天在{place}待了挺久，脑子里乱乱的。",
                        "你问得好突然。……还行吧，就是有点累。",
                        "这个嘛，等我想清楚了再告诉你。",
                    ]
                ),
                "influence": None,
            }
        return {
            "reply": rng.choice(
                ["收到。你今天话有点多哦。", "嗯，我在听。", "哈，你这么说我反而不知道回什么了。", "谢谢你。真的。"]
            ),
            "influence": None,
            "mood": rng.choice(["平静", "放松了一点"]),
        }

    def _fake_slot(self, ctx: Mapping[str, Any], rng: random.Random) -> dict:
        names = {loc["id"]: loc["name"] for loc in ctx["locations"]}
        npcs = list(ctx["npcs"])
        decisions, companion = self._fake_decisions(ctx, rng, npcs)
        if companion is not None:
            place = companion["location"]
        else:
            options = [p for p in _SLOT_PLACES.get(ctx["slot"], []) if p in names] or list(names)
            place = rng.choice(options)
            nearby = [npc for npc in npcs if npc["location"] == place]
            companion = rng.choice(nearby) if nearby and rng.random() < 0.7 else None
        activity = rng.choice(_ACTIVITIES.get(place, ["发了一会儿呆"]))
        hero = ctx.get("protagonist", "她")
        if companion is not None:
            scene = (
                f"{ctx['slot_label']}，{hero}在{names[place]}{activity}，碰到了{companion['name']}。"
                + rng.choice(
                    [
                        "两人聊了几句不痛不痒的话，气氛比想象中轻松。",
                        "对方欲言又止，最后只说了句“回头再说”。",
                        "她本想多问几句，话到嘴边又咽了回去。",
                    ]
                )
            )
        else:
            scene = f"{ctx['slot_label']}，{hero}一个人在{names[place]}{activity}，时间过得很慢。"
        return {
            "location": place,
            "with": [companion["id"]] if companion else [],
            "title": activity,
            "scene": scene,
            "mood": rng.choice(["平静", "有点烦", "松了口气", "闷闷的", "小小地开心"]),
            "memory": f"{ctx['slot_label']}在{names[place]}{activity}"
            + (f"，遇到了{companion['name']}。" if companion else "。"),
            "relationship_changes": (
                [{"npc": companion["id"], "delta": rng.choice([-3, -1, 2, 3, 5]), "reason": "这次相处的感觉"}]
                if companion
                else []
            ),
            "influence_decisions": decisions,
            "discoveries": (
                [{"npc": companion["id"], "fact": companion["hidden"]}]
                if companion and companion.get("hidden") and rng.random() < 0.15
                else []
            ),
            "npc_updates": [
                {"npc": npc["id"], "location": rng.choice(list(names)), "status": rng.choice(_NPC_STATUS)}
                for npc in rng.sample(npcs, k=min(2, len(npcs)))
                if companion is None or npc["id"] != companion["id"]
            ],
        }

    def _fake_review(self, ctx: Mapping[str, Any], rng: random.Random) -> dict:
        titles = [scene["title"] for scene in ctx.get("scenes", [])]
        day = ctx.get("day", 1)
        letter = None
        if rng.random() < 0.35 or (ctx.get("chat_count", 0) == 0 and day % 2 == 0):
            letter = {
                "title": rng.choice(["今天的事", "睡不着，写给你", "一点小事"]),
                "body": "笔友：\n\n今天"
                + "、".join(titles[:3])
                + "。说出来好像也没什么，可写下来就觉得轻了一点。\n\n你那边呢？\n\n林夏",
            }
        return {
            "summary": f"第{day}天：" + "；".join(titles) + "。" if titles else f"第{day}天平平常常地过去了。",
            "diary": rng.choice(
                ["今天好像什么都没发生，又好像发生了很多。", "有点累。明天再想吧。", "写了半页稿子，又全删了。"]
            ),
            "focus": rng.choice(["把征文的开头写出来", "找机会和许念说上话", "别在课上睡着"]),
            "letter": letter,
        }

    def _fake_offscreen_day(self, ctx: Mapping[str, Any], rng: random.Random) -> dict:
        slot = rng.choice([3, 4])
        slot_output = self._fake_slot({**ctx, "slot": slot, "slot_label": _FAKE_SLOT_LABELS[slot]}, rng)
        return {
            "summary": slot_output["scene"],
            "highlights": [
                {"title": slot_output["title"], "location": slot_output["location"], "with": slot_output["with"]}
            ],
            "diary": rng.choice(
                ["笔友今天也没上线。", "今天写了一点稿子，不知道好不好。", "放学路上看到许念了，没敢打招呼。"]
            ),
            "mood": slot_output["mood"],
            "memory": slot_output["memory"],
            "focus": rng.choice(["把征文写完", "等笔友回消息"]),
            "relationship_changes": slot_output["relationship_changes"],
            "influence_decisions": slot_output["influence_decisions"],
            "discoveries": slot_output["discoveries"],
            "npc_updates": slot_output["npc_updates"],
        }

    def _fake_letter(self, ctx: Mapping[str, Any], rng: random.Random) -> dict:
        diaries = [f"第{item['day']}天：{item['text']}" for item in ctx.get("diaries", [])]
        days = ctx.get("days_away", 1)
        return {
            "title": rng.choice(["你回来了", "这几天", "给消失的笔友"]),
            "body": f"笔友：\n\n你消失了{days}天。我把这几天记下来了：\n"
            + "\n".join(diaries[-3:])
            + "\n\n也没什么大事。就是……你回来了就好。\n\n林夏",
        }

    @staticmethod
    def _fake_decisions(
        ctx: Mapping[str, Any], rng: random.Random, npcs: list[Mapping[str, Any]]
    ) -> tuple[list[dict], Mapping[str, Any] | None]:
        decisions, companion = [], None
        for influence in ctx.get("pending", []):
            roll = rng.random()
            if roll < 0.6:
                decisions.append(
                    {"id": influence["id"], "decision": "adopted", "reason": "想了想，笔友说得有道理，试一次也不会怎样。"}
                )
                if companion is None and influence.get("target"):
                    companion = next((npc for npc in npcs if npc["id"] == influence["target"]), None)
            elif roll < 0.85:
                decisions.append(
                    {"id": influence["id"], "decision": "declined", "reason": "现在还不是时候，她也不想被人推着走。"}
                )
            else:
                decisions.append({"id": influence["id"], "decision": "deferred", "reason": "还没想好，先放一放。"})
        return decisions, companion


_SUGGESTION_WORDS = ("去", "试试", "要不要", "建议", "应该", "找", "别", "不如")

_SLOT_PLACES = {
    1: ["classroom", "school_gate"],
    2: ["classroom"],
    3: ["library", "playground", "classroom"],
    4: ["club_room", "home", "playground", "school_gate"],
}

_ACTIVITIES = {
    "classroom": ["听课走神", "和同桌闲聊", "补昨天的笔记"],
    "school_gate": ["在校门口等人", "买了杯热豆浆"],
    "library": ["躲在角落写稿", "翻旧杂志找灵感"],
    "club_room": ["参加社团讨论", "被社长点名改稿"],
    "playground": ["在场边看篮球赛", "绕着跑道走了两圈"],
    "home": ["一个人吃晚饭", "在台灯下改稿子"],
}

_NPC_STATUS = ["在赶作业", "在发呆", "在和别人说话", "匆匆走过", "在看书"]

_FAKE_SLOT_LABELS = {3: "午后", 4: "放学后"}
