"use strict";

const $ = (selector) => document.querySelector(selector);
const STATUS_TEXT = { pending: "还在考虑", deferred: "先放一放", adopted: "采纳了", declined: "没有采纳" };
const KIND_TEXT = { scene: "", day_review: "当日回顾", offscreen_day: "你不在的时候", sleep: "休眠", world_start: "开始" };

let current = null;
let busy = false;
let seenEvents = new Set();
let pendingLetterId = null;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

async function api(path, body) {
  const options = body === undefined
    ? {}
    : { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) };
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function toast(message, isError = false) {
  const node = $("#toast");
  node.textContent = message;
  node.className = isError ? "toast error" : "toast";
  node.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { node.hidden = true; }, isError ? 6000 : 3000);
}

function setBusy(flag, label = "") {
  busy = flag;
  document.body.classList.toggle("busy", flag);
  for (const id of ["#advance", "#send", "#away", "#restart"]) $(id).disabled = flag;
  $("#busy-label").textContent = flag ? label : "";
}

async function run(label, task) {
  if (busy) return null;
  setBusy(true, label);
  try {
    return await task();
  } catch (error) {
    toast(error.message, true);
    return null;
  } finally {
    setBusy(false);
  }
}

function slotLabel(slot) {
  return (current && current.slots[slot - 1]) || `时段${slot}`;
}

// Rendering ---------------------------------------------------------------------

function render(state) {
  current = state;
  $("#clock").textContent = `第 ${state.time.day} 天 · ${state.time.label}`;
  $("#clock").title = state.time.hint;
  $("#model").textContent = state.llm.startsWith("fake") ? "离线假模型" : state.llm;
  $("#model").title = state.llm.startsWith("fake") ? "没有配置 API key，回复由规则生成" : "";
  $("#p-name").textContent = state.protagonist.name;
  $("#p-sub").textContent = `${state.protagonist.role} · ${state.protagonist.mood}`;
  $("#avatar").textContent = state.protagonist.name.slice(-1);
  $("#premise").textContent = state.world.premise;
  renderMessages(state);
  renderStatus(state);
  renderLetters(state);
  renderPeople(state);
  renderTimeline(state);
  renderDebug(state);
}

function renderMessages(state) {
  const box = $("#messages");
  const byMessage = new Map(state.influences.map((item) => [item.message_id, item]));
  box.replaceChildren();
  if (!state.messages.length) {
    box.append(el("div", "empty", "她还不知道你是谁。打个招呼吧。"));
    return;
  }
  for (const message of state.messages) {
    const row = el("div", `msg ${message.role}`);
    row.append(el("div", "bubble", message.text));
    const influence = byMessage.get(message.id);
    if (influence) {
      const chip = el("div", `chip ${influence.status}`, `她记下了：${influence.text} · ${STATUS_TEXT[influence.status]}`);
      if (influence.reason) chip.title = influence.reason;
      row.append(chip);
    }
    row.append(el("div", "meta", `第${message.day}天 · ${slotLabel(message.slot)}`));
    box.append(row);
  }
  box.scrollTop = box.scrollHeight;
}

function renderStatus(state) {
  const status = $("#status");
  status.replaceChildren();
  for (const [label, value] of [
    ["心情", state.protagonist.mood],
    ["在哪", state.protagonist.location],
    ["在意", state.protagonist.focus],
  ]) {
    status.append(el("dt", null, label), el("dd", null, value));
  }
  const facts = $("#facts");
  facts.replaceChildren();
  if (state.protagonist.known_facts.length) {
    facts.className = "facts";
    facts.append(el("strong", null, "她最近才知道的事"));
    const list = el("ul");
    for (const fact of state.protagonist.known_facts) list.append(el("li", null, `${fact.npc}：${fact.fact}`));
    facts.append(list);
  } else {
    facts.className = "";
  }
}

function renderLetters(state) {
  const list = $("#letters");
  list.replaceChildren();
  $("#unread").textContent = state.unread_letters ? String(state.unread_letters) : "";
  if (!state.letters.length) {
    list.append(el("li", "empty", "还没有来信。"));
    return;
  }
  for (const letter of state.letters) {
    const item = el("li", letter.read ? "" : "unread");
    item.append(el("span", "letter-name", letter.title), el("span", "when", `第${letter.day}天`));
    item.addEventListener("click", () => openLetter(letter.id));
    list.append(item);
  }
}

function renderPeople(state) {
  const list = $("#people");
  list.replaceChildren();
  for (const person of state.relationships) {
    const item = el("li");
    const top = el("div", "person-top");
    const who = el("span", null, person.name);
    who.append(" ", el("span", "person-role", person.role));
    top.append(who, el("span", "person-role", `${person.affinity}/100`));
    const bar = el("div", "bar");
    const fill = el("span");
    fill.style.width = `${person.affinity}%`;
    bar.append(fill);
    item.append(top, bar, el("div", "person-note", person.last_reason ? `最近：${person.last_reason}` : person.note));
    list.append(item);
  }
}

function renderTimeline(state) {
  const list = $("#timeline");
  list.replaceChildren();
  const first = seenEvents.size === 0;
  for (const event of state.timeline) {
    const item = el("li", event.kind);
    if (!first && !seenEvents.has(event.id)) item.classList.add("fresh");
    const wholeDay = ["day_review", "offscreen_day", "sleep"].includes(event.kind);
    const kind = KIND_TEXT[event.kind] ? ` · ${KIND_TEXT[event.kind]}` : "";
    item.append(el("div", "event-when", `第${event.day}天${wholeDay ? "" : ` · ${event.slot_label}`}${kind}`));
    if (event.kind !== "day_review") {
      const title = el("div", "event-title", event.title);
      if (event.fallback) title.append(el("span", "badge", "规则兜底"));
      item.append(title);
    }
    item.append(el("p", "event-summary", event.summary));
    const tags = [];
    if (event.location) tags.push(`📍${event.location}`);
    if (event.with.length) tags.push(`和 ${event.with.join("、")}`);
    const extraHighlights = event.highlights.filter((text) => text !== event.title);
    if (extraHighlights.length) tags.push(extraHighlights.join(" / "));
    if (tags.length) item.append(el("div", "event-tags", tags.join(" · ")));
    for (const cause of event.causes) {
      const reason = cause.reason ? `：${cause.reason}` : "";
      item.append(el("div", `cause ${cause.decision}`, `因为你说过「${cause.text}」→ ${STATUS_TEXT[cause.decision]}${reason}`));
    }
    list.append(item);
  }
  seenEvents = new Set(state.timeline.map((event) => event.id));
}

function renderDebug(state) {
  const panel = $("#debug-panel");
  panel.replaceChildren();
  panel.append(el("h4", null, "人物的真实状态"));
  const npcs = el("ul");
  for (const npc of state.debug.npcs) {
    const item = el("li", null, `${npc.name}（${npc.role}）在${npc.location}${npc.status ? "，" + npc.status : ""}`);
    item.append(el("div", "secret", `隐藏：${npc.hidden}`));
    npcs.append(item);
  }
  panel.append(npcs, el("h4", null, "她的记忆（最近）"));
  const memories = el("ul");
  for (const memory of state.debug.memories) memories.append(el("li", null, `第${memory.day}天：${memory.text}`));
  if (!state.debug.memories.length) memories.append(el("li", null, "（还没有）"));
  panel.append(memories, el("h4", null, "世界"));
  panel.append(el("div", null, `${state.world.name} · ${state.world.id} · 模型 ${state.llm}`));
}

// Actions -------------------------------------------------------------------------

async function openLetter(letterId) {
  const letter = current.letters.find((item) => item.id === letterId);
  if (!letter) return;
  $("#letter-title").textContent = letter.title;
  $("#letter-meta").textContent = `第${letter.day}天 · 来自${current.protagonist.name}`;
  $("#letter-body").textContent = letter.body;
  $("#letter-dialog").showModal();
  if (!letter.read) {
    try {
      render((await api(`/api/letters/${letterId}/read`, {})).state);
    } catch (error) {
      toast(error.message, true);
    }
  }
}

function showCatchUp(report) {
  if (!report || !report.days_away) return;
  const slept = report.slept ? "，之后进入了休眠" : "";
  $("#banner-text").textContent =
    `你离开了 ${report.days_away} 天。${current.protagonist.name}的世界继续走了 ${report.simulated_days} 天${slept}。她给你写了一封信。`;
  pendingLetterId = report.letter_id;
  $("#banner").hidden = false;
}

async function sendMessage(event) {
  event.preventDefault();
  const input = $("#input");
  const text = input.value.trim();
  if (!text || busy) return;
  input.value = "";
  const box = $("#messages");
  box.querySelector(".empty")?.remove();
  const mine = el("div", "msg player");
  mine.append(el("div", "bubble", text));
  const typing = el("div", "msg protagonist typing");
  typing.append(el("div", "bubble", "正在输入…"));
  box.append(mine, typing);
  box.scrollTop = box.scrollHeight;
  const clientId = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
  const data = await run("她正在输入…", () => api("/api/message", { text, client_id: clientId }));
  if (data) {
    render(data.state);
    if (data.result.influence) toast(`她记下了你的建议：${data.result.influence.text}`);
  } else {
    mine.remove();
    typing.remove();
    input.value = text;
  }
  input.focus();
}

async function advance() {
  const data = await run("世界推进中…", () => api("/api/advance", {}));
  if (!data) return;
  render(data.state);
  if (data.result.letter_id) toast("她给你写了一封信");
}

async function away(days) {
  const data = await run(`补算离开的 ${days} 天…`, () => api("/api/dev/away", { days }));
  if (!data) return;
  render(data.state);
  showCatchUp(data.result);
}

async function restart() {
  if (!confirm("重新开始会创建一个新世界（旧世界留在数据库里）。确定吗？")) return;
  const data = await run("创建新世界…", () => api("/api/world/new", {}));
  if (!data) return;
  seenEvents = new Set();
  $("#banner").hidden = true;
  render(data.state);
}

function setDebug(on) {
  document.body.classList.toggle("debug", on);
  $("#debug").checked = on;
  try { localStorage.setItem("tr-debug", on ? "1" : "0"); } catch { /* storage unavailable */ }
}

// Wiring --------------------------------------------------------------------------

$("#composer").addEventListener("submit", sendMessage);
$("#input").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault();
    $("#composer").requestSubmit();
  }
});
$("#advance").addEventListener("click", advance);
$("#restart").addEventListener("click", restart);
$("#away").addEventListener("click", () => {
  $("#away-dialog").returnValue = "";
  $("#away-dialog").showModal();
});
$("#away-dialog").addEventListener("close", () => {
  if ($("#away-dialog").returnValue !== "ok") return;
  const days = Math.max(1, Math.min(30, Number($("#away-days").value) || 1));
  away(days);
});
$("#debug").addEventListener("change", (event) => setDebug(event.target.checked));
$("#banner-close").addEventListener("click", () => { $("#banner").hidden = true; });
$("#banner-letter").addEventListener("click", () => {
  $("#banner").hidden = true;
  if (pendingLetterId) openLetter(pendingLetterId);
});

(async function start() {
  const fromUrl = new URLSearchParams(location.search).get("debug");
  try {
    setDebug(fromUrl !== null ? fromUrl === "1" : localStorage.getItem("tr-debug") === "1");
  } catch {
    setDebug(fromUrl === "1");
  }
  const data = await run("连接中…", () => api("/api/session", {}));
  if (!data) return;
  render(data.state);
  showCatchUp(data.result);
})();
