/*
  MindMesh
  File: advanced.js
  Version: 1.5
  Date: 12.02.2026
  Purpose:
  - Advanced assistant сценарий
  - i18n
  - Защита от потери данных
  - Валидация ввода
  - UI v3 complete
*/

let session_id = null;
let saved = false;
let waitingChoice = false;
let isDirty = false;
window.isDirty = false;

// ================== VALIDATION ==================

function looksLikeHumanText(text) {
  if (!text) return false;
  const t = text.trim();
  if (t.length < 4) return false;

  const letters = t.match(/[a-zA-Zа-яА-Яא-ת]/g) || [];
  if (letters.length / t.length < 0.5) return false;

  const uniqueChars = new Set(t).size;
  if (uniqueChars / t.length < 0.3) return false;

  const words = t.split(/\s+/).filter(w => w.length >= 3);
  if (words.length === 0) return false;

  return true;
}

// ================== UI ==================

function addMsg(who, text) {
  const chat = document.getElementById("chat");

  const div = document.createElement("div");
  div.classList.add("message");

  if (who === t("user")) div.classList.add("user");
  else div.classList.add("assistant");

  div.innerText = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function clearChat() {
  if (isDirty && !saved) {
    if (!confirm("Очистить текущую сессию? Несохранённые данные будут потеряны.")) return;
  }
  document.getElementById("chat").innerHTML = "";
  isDirty = false;
  window.isDirty = false;
}

function newSession() {
  if (isDirty && !saved) {
    if (!confirm("Начать новую сессию? Несохранённые данные будут потеряны.")) return;
  }
  start();
}

// ================== FLOW ==================

async function start() {
  const r = await fetch("/api/advanced/start", { method: "POST" });
  const j = await r.json();

  session_id = j.session_id;
  saved = false;
  waitingChoice = false;
  isDirty = false;
  window.isDirty = false;

  document.getElementById("chat").innerHTML = "";

  if (j.message_key) addMsg(t("assistant"), t(j.message_key));
  else if (j.message) addMsg(t("assistant"), j.message);
}

async function sendMsg() {
  if (saved || waitingChoice) return;

  const inp = document.getElementById("msg");
  const text = inp.value.trim();
  if (!text) return;

  if (!looksLikeHumanText(text)) {
    addMsg(t("system"), t("validation_bad_text"));
    return;
  }

  inp.value = "";
  addMsg(t("user"), text);

  isDirty = true;
  window.isDirty = true;

  const form = new FormData();
  form.append("session_id", session_id);
  form.append("message", text);

  const r = await fetch("/api/advanced/message", { method: "POST", body: form });
  const j = await r.json();

  if (j.reply_key) addMsg(t("assistant"), t(j.reply_key));
  else if (j.reply) addMsg(t("assistant"), j.reply);
}

// ================== ENTER ==================

document.addEventListener("DOMContentLoaded", function () {
  const inp = document.getElementById("msg");
  if (!inp) return;

  inp.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMsg();
    }
  });
});

// ================== SAFETY ==================

window.addEventListener("beforeunload", function (e) {
  if (window.isDirty && !saved) {
    e.preventDefault();
    e.returnValue = "";
  }
});

window.addEventListener("languageChanged", function () {
  start();
});

start();
