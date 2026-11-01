"""Prompt builders.

Narrator prompts (slot, offscreen day) may see hidden NPC facts so characters act
consistently. Protagonist prompts (chat, letters) and the day review never do: they
only see what the protagonist experienced, remembers, or has discovered.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

INFLUENCE_STATUS = {
    "pending": "还在考虑",
    "deferred": "先放一放",
    "adopted": "采纳了",
    "declined": "没有采纳",
}

SLOT_SCHEMA = """{
  "location": "主角这个时段所在的地点id",
  "with": ["一起出现的人物id，可以为空"],
  "title": "发生了什么，12个字以内",
  "scene": "第三人称场景，80到200字，可以有一两句对话",
  "mood": "主角之后的心情，2到6个字",
  "memory": "主角会记住的一句话，第一人称",
  "relationship_changes": [{"npc": "人物id", "delta": 0, "reason": "原因"}],
  "influence_decisions": [{"id": "建议id", "decision": "adopted 或 declined 或 deferred", "reason": "主角自己的理由"}],
  "discoveries": [{"npc": "人物id", "fact": "主角在这个场景里确实得知的新信息"}],
  "npc_updates": [{"npc": "人物id", "location": "地点id", "status": "此刻在做什么，10个字以内"}]
}
每条待决定的建议都要在 influence_decisions 里给出决定。delta 是 -10 到 10 的整数。没有的项写空数组。"""

OFFSCREEN_SCHEMA = """{
  "summary": "这一天的概括，第三人称，80到160字",
  "highlights": [{"title": "12个字以内", "location": "地点id", "with": ["人物id"]}],
  "diary": "她当晚的日记，第一人称，60到120字，只写她自己知道的事",
  "mood": "她的心情，2到6个字",
  "memory": "她会记住的一句话，第一人称",
  "focus": "明天她最在意的事，一句话",
  "relationship_changes": [{"npc": "人物id", "delta": 0, "reason": "原因"}],
  "influence_decisions": [{"id": "建议id", "decision": "adopted 或 declined 或 deferred", "reason": "主角自己的理由"}],
  "discoveries": [{"npc": "人物id", "fact": "她这一天确实得知的新信息"}],
  "npc_updates": [{"npc": "人物id", "location": "地点id", "status": "此刻在做什么，10个字以内"}]
}
highlights 写 1 到 3 条。每条待决定的建议都要给出决定。delta 是 -10 到 10 的整数。没有的项写空数组。"""


def protagonist_system(bp: Mapping[str, Any]) -> str:
    p, world = bp["protagonist"], bp["world"]
    return "\n".join(
        [
            f"你在一个互动故事里扮演{p['name']}，{p['age']}岁，{p['role']}。",
            f"性格：{p['personality']}",
            f"说话方式：{p['speech_style']}",
            f"看重：{'、'.join(p['values'])}",
            f"绝不会做：{'、'.join(p['taboos'])}",
            f"心里的目标：{'；'.join(p['goals'])}",
            f"害怕：{'；'.join(p['fears'])}",
            "",
            f"世界：{world['setting']}",
            "你和对方的关系：对方是你偶然加上的匿名笔友，你不知道TA是谁，只通过文字联系。"
            "TA看不到你的生活，只知道你告诉TA的事。",
            "",
            "规则：",
            "- 只说你亲身经历过、记得或被人告诉过的事。别人的秘密你不知道，除非它出现在“你知道的事”里。",
            "- 认真对待笔友的建议，但你有自己的判断，可以拒绝、讨价还价或者先放一放。",
            "- 不要假装知道笔友的现实生活。",
            "- 用中文。聊天时像真人发消息一样自然，不写旁白，不写括号里的动作。",
        ]
    )


def narrator_system(bp: Mapping[str, Any]) -> str:
    p = bp["protagonist"]
    return "\n".join(
        [
            f"你是校园生活模拟“{bp['world']['name']}”的叙事引擎，负责推进主角{p['name']}的日常。",
            "原则：",
            "- 真实、克制、有生活细节。不是每个时段都要发生大事，平淡的时段也可以有小情绪。",
            "- 每个人物按自己的性格、目标和隐藏信息行事。隐藏信息只有在场景里真的被揭示时，主角才会知道；"
            "没有揭示时，场景描写里也不要点破。",
            "- 主角有自己的主见，不是笔友的提线木偶：笔友的建议她会考虑，但最终由她自己决定。",
            "- 关系变化要小，并且有具体理由。",
            "- 只输出一个 JSON 对象，不要其他文字。",
        ]
    )


def chat_prompt(
    bp: Mapping[str, Any],
    state: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    text: str,
) -> str:
    hero = state["protagonist"]
    npc_ids = ", ".join(f"{npc['id']}={npc['name']}" for npc in bp["npcs"])
    lines = [
        f"【现在】{_time(bp, state)}，你在{_location(bp, hero['location'])}。"
        f"心情：{hero['mood']}。最在意的事：{hero['focus']}",
        "",
        *_protagonist_view(bp, state),
        "",
        "【笔友之前的建议】",
        *(
            [
                f"- {item['text']}（{INFLUENCE_STATUS[item['status']]}）"
                for item in state["influences"][-5:]
            ]
            or ["- （没有）"]
        ),
        "",
        "【最近的聊天】",
        *(
            [("笔友：" if m["role"] == "player" else "你：") + m["text"] for m in history]
            or ["（这是你们第一次聊天）"]
        ),
        "",
        "【笔友刚发来】",
        text,
        "",
        "只输出一个 JSON 对象，不要其他文字：",
        '{"reply": "你的回复，1到4句", "influence": null, "mood": "聊完后的心情，2到6个字，可省略"}',
        "如果笔友提出了具体的建议或请求（比如去找谁、做什么、别做什么），把 influence 写成：",
        '{"text": "一句话概括你接收到的建议", "target": "涉及的人物id，没有就写null"}',
        f"人物id：{npc_ids}",
    ]
    return "\n".join(lines)


def slot_prompt(
    bp: Mapping[str, Any],
    state: Mapping[str, Any],
    recent_events: Sequence[Mapping[str, Any]],
) -> str:
    slot = bp["slots"][state["slot"] - 1]
    lines = [
        f"【世界】{bp['world']['setting']}",
        f"【时段】{_time(bp, state)}（{slot['hint']}）",
    ]
    if state["slot"] == len(bp["slots"]):
        lines.append("【注意】这是今天最后一个时段，结束时主角会回到家。")
    lines += [
        "",
        *_narrator_view(bp, state, recent_events),
        "",
        "只输出一个 JSON 对象：",
        SLOT_SCHEMA,
    ]
    return "\n".join(lines)


def offscreen_prompt(
    bp: Mapping[str, Any],
    state: Mapping[str, Any],
    recent_events: Sequence[Mapping[str, Any]],
) -> str:
    slot = bp["slots"][state["slot"] - 1]
    lines = [
        f"【世界】{bp['world']['setting']}",
        f"【说明】笔友这段时间没有上线。请用一次输出概括第{state['day']}天"
        f"从{slot['label']}到一天结束的生活，结束时主角回到家。",
        "",
        *_narrator_view(bp, state, recent_events),
        "",
        "只输出一个 JSON 对象：",
        OFFSCREEN_SCHEMA,
    ]
    return "\n".join(lines)


def review_prompt(
    bp: Mapping[str, Any],
    state: Mapping[str, Any],
    scenes: Sequence[Mapping[str, Any]],
    chat_count: int,
) -> str:
    p = bp["protagonist"]
    lines = [
        f"第{state['day']}天结束了。{p['name']}今天经历了：",
        *[f"- {scene['slot_label']}：{scene['title']}——{_clip(scene['summary'], 160)}" for scene in scenes],
        f"今天她和笔友聊了{chat_count}条消息。她最在意的事：{state['protagonist']['focus']}",
        "",
        "只输出一个 JSON 对象：",
        '{"summary": "今天的摘要，第三人称，60到120字",',
        ' "diary": "她今晚的日记，第一人称，80到150字，只写她自己知道的事",',
        ' "focus": "明天她最在意的事，一句话",',
        ' "letter": null}',
        "如果今天发生了让她特别想告诉笔友的事，或者她有话想问笔友，就把 letter 写成"
        '{"title": "信的标题", "body": "写给笔友的信，第一人称，100到250字，只写她知道的事"}。'
        "不是每天都要写信。",
    ]
    return "\n".join(lines)


def absence_letter_prompt(
    bp: Mapping[str, Any],
    state: Mapping[str, Any],
    days_away: int,
    slept: bool,
    diaries: Sequence[Mapping[str, Any]],
) -> str:
    hero = state["protagonist"]
    lines = [
        f"笔友已经{days_away}天没有上线了。这些天你的日记：",
        *([f"- 第{item['day']}天：{item['text']}" for item in diaries] or ["- （没有记下什么）"]),
    ]
    if slept:
        lines.append("再后来的日子你没有记下来，好像整个世界都停了一下。")
    lines += [
        f"你现在的心情：{hero['mood']}。最在意的事：{hero['focus']}",
        "",
        "给笔友写一封信，第一人称，150到300字：说说这几天的事和心情，也可以问TA去哪了。"
        "只写你自己知道的事，不要编造笔友的生活。",
        '只输出一个 JSON 对象：{"title": "信的标题", "body": "信的正文"}',
    ]
    return "\n".join(lines)


def _protagonist_view(bp: Mapping[str, Any], state: Mapping[str, Any]) -> list[str]:
    hero = state["protagonist"]
    npcs = {npc["id"]: npc for npc in bp["npcs"]}
    relationships = []
    for npc_id, rel in state["relationships"].items():
        recent = f"；最近：{rel['last_reason']}" if rel["last_reason"] else ""
        relationships.append(
            f"- {npcs[npc_id]['name']}（{npcs[npc_id]['role']}）：{rel['note']}{recent}（亲近度 {rel['affinity']}/100）"
        )
    return [
        "【你记得的最近的事】",
        *([f"- {m['text']}" for m in hero["memories"][-8:]] or ["- （还没什么特别的）"]),
        "【前几天的日记】",
        *([f"- 第{d['day']}天：{d['text']}" for d in state["diaries"][-3:]] or ["- （还没有）"]),
        "【你知道的事】",
        *([f"- {npcs[f['npc']]['name']}：{f['fact']}" for f in hero["known_facts"]] or ["- （没有特别的）"]),
        "【你对身边人的看法】",
        *relationships,
    ]


def _narrator_view(
    bp: Mapping[str, Any],
    state: Mapping[str, Any],
    recent_events: Sequence[Mapping[str, Any]],
) -> list[str]:
    p, hero = bp["protagonist"], state["protagonist"]
    npc_lines = []
    for npc in bp["npcs"]:
        now = state["npcs"][npc["id"]]
        rel = state["relationships"][npc["id"]]
        npc_lines.append(
            f"- {npc['id']} {npc['name']}｜{npc['role']}｜{npc['personality']}｜隐藏：{npc['hidden']}"
            f"｜现在在{_location(bp, now['location'])}{('，' + now['status']) if now['status'] else ''}"
            f"｜和主角：{rel['affinity']}/100，{rel['note']}"
        )
    pending = [item for item in state["influences"] if item["status"] in ("pending", "deferred")]
    return [
        f"【主角】{p['name']}，{p['role']}。{p['personality']}",
        f"目标：{'；'.join(p['goals'])}。害怕：{'；'.join(p['fears'])}。底线：{'、'.join(p['taboos'])}。",
        f"现在在{_location(bp, hero['location'])}，心情{hero['mood']}，最在意：{hero['focus']}",
        "【主角最近的记忆】",
        *([f"- {m['text']}" for m in hero["memories"][-6:]] or ["- （还没有）"]),
        "【主角已经知道的事】",
        *([f"- {f['npc']}：{f['fact']}" for f in hero["known_facts"]] or ["- （没有）"]),
        "【最近发生的事】",
        *(
            [f"- 第{e['day']}天 {e['title']}：{_clip(e['summary'], 80)}" for e in reversed(recent_events)]
            or ["- （刚开学）"]
        ),
        "【人物（包含主角不知道的隐藏信息，只用来安排情节）】",
        *npc_lines,
        "【地点】" + "，".join(f"{loc['id']}={loc['name']}" for loc in bp["locations"]),
        "【笔友的建议，等主角自己决定】",
        *(
            [
                f"- {item['id']}：{item['text']}"
                + (f"（涉及 {item['target']}）" if item.get("target") else "")
                for item in pending
            ]
            or ["- （没有）"]
        ),
    ]


def _time(bp: Mapping[str, Any], state: Mapping[str, Any]) -> str:
    return f"第{state['day']}天{bp['slots'][state['slot'] - 1]['label']}"


def _location(bp: Mapping[str, Any], location_id: str) -> str:
    return next((loc["name"] for loc in bp["locations"] if loc["id"] == location_id), location_id)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
