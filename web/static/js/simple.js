/*
  MindMesh
  File: simple.js
  Version: 3.5
  Date: 28.02.2026
  Fix:
  - Keep ALL existing modules/flows (no cuts)
  - Similarity: normalize + pretty percent output (0..1 -> 0..100)
  - Use safe i18n fallback helper for modal texts
  - Analyze button uses requestSubmit() when available
  - classifyError(): use mm_t() (not t()) to avoid runtime errors
  - Fallback text uses formatted similarity
*/

document.addEventListener("DOMContentLoaded", function () {

  let currentAnalysis = null;
  let currentDuplicateId = null;
  let currentDuplicateTitle = null;
  let currentSimilarity = 0;
  let pendingAuthorEmail = null;
  let pendingAuthorFirstName = null;
  let pendingAuthorLastName = null;

  // ================= HELPERS =================

  function el(id) { return document.getElementById(id); }

  function getUserFromDataset() {
    const card = document.querySelector(".simple-card");
    if (!card) return { name: "", email: "" };
    return {
      name: (card.dataset.username || "").trim(),
      email: (card.dataset.useremail || "").trim()
    };
  }

  function showBlock(blockId) {
    const ids = ["simpleStepInput", "simpleStepPreview", "simpleStepEdit"];
    ids.forEach(id => {
      const node = el(id);
      if (!node) return;
      node.style.display = (id === blockId) ? "block" : "none";
    });
  }

  // Similarity normalization:
  // - If server returns 0..1 => convert to 0..100
  // - If already 0..100 => keep
  // - Clamp 0..100 and format to 1 decimal
  function normalizeSimilarity(value) {
    let v = Number(value);
    if (!isFinite(v)) v = 0;

    // heuristic: if 0..1, treat as fraction
    if (v > 0 && v <= 1) v = v * 100;

    // clamp
    if (v < 0) v = 0;
    if (v > 100) v = 100;

    return v;
  }

  function formatSimilarityPercent(value) {
    const v = normalizeSimilarity(value);
    // 1 decimal looks nice; you can change to 0 decimals if needed
    return v.toFixed(1) + "%";
  }

  // ================= MODAL =================

  function showModal(title, text, buttons = []) {
    const overlay = el("mmModalOverlay");
    const titleEl = el("mmModalTitle");
    const bodyEl = el("mmModalBody");
    const actionsEl = el("mmModalActions");

    if (!overlay || !titleEl || !bodyEl || !actionsEl) {
      console.error("Modal elements not found in DOM");
      return;
    }

    titleEl.innerText = title;
    bodyEl.innerText = text;

    actionsEl.innerHTML = "";

    if (!buttons || buttons.length === 0) {
      buttons = [{
        text: "OK",
        class: "btn primary",
        onClick: () => { overlay.style.display = "none"; }
      }];
    }

    buttons.forEach(btn => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = btn.class || "btn primary";
      b.innerText = btn.text || "OK";
      b.onclick = function () {
        overlay.style.display = "none";
        if (btn.onClick) btn.onClick();
      };
      actionsEl.appendChild(b);
    });

    overlay.style.display = "flex";
  }

  // ================= FALLBACK + I18N (RU/EN/HE) =================

  function mm_t(key, vars) {
    let s = null;

    try {
      if (typeof window.t === "function") s = window.t(key);
      else if (typeof window.i18n === "function") s = window.i18n(key);
      else if (typeof window.translate === "function") s = window.translate(key);
      else if (window.I18N && typeof window.I18N.t === "function") s = window.I18N.t(key);
      else if (window.translations) {
        const lang = window.currentLang || window.lang || document.documentElement.lang || "en";
        const dict = window.translations[lang] || window.translations;
        s = dict && dict[key];
      }
    } catch (e) {
      // ignore
    }

    if (!s) s = key;

    if (vars && typeof vars === "object") {
      Object.keys(vars).forEach(k => {
        s = s.split("{" + k + "}").join(String(vars[k]));
      });
    }

    return s;
  }

  // safe translator with fallback text
  function tr(key, fallback, vars) {
    const s = mm_t(key, vars);
    return (s === key) ? (fallback || key) : s;
  }

  // ================= PREVIEW RENDER =================

  function renderPreviewFromAnalysis(analysis, similarity, duplicateTitle) {
    if (!analysis) return;

    el("pv_full").innerText = analysis.full || "";

    const u = getUserFromDataset();

    // если есть email из edit — используем его
    const editEmail = el("edit_email") ? el("edit_email").value : "";
    const editName = el("edit_name") ? el("edit_name").value : "";

    el("pv_author").innerText =
      (editName || u.name || tr("assistant_author_anonymous", "Anonymous")).trim();

    el("pv_email").innerText =
      (editEmail || u.email || "").trim();

    el("pv_title").innerText = analysis.title || "";
    el("pv_short").innerText = analysis.short || "";
    el("pv_keywords").innerText = (analysis.keywords || []).join(", ");
    el("pv_type").innerText = analysis.idea_type || "Idea";

    // ✅ pretty similarity
    el("pv_similarity").innerText = formatSimilarityPercent(similarity);

    const dupBlock = el("dupBlock");
    const dupText = el("dupText");

    if (duplicateTitle && dupBlock && dupText) {
      dupBlock.style.display = "block";
      dupText.innerText = tr("simple_duplicate_label", "Похожая идея: ") + duplicateTitle;
    } else if (dupBlock) {
      dupBlock.style.display = "none";
    }
  }

  // ================= ANALYZE (FORM SUBMIT) =================

  const form = el("simpleForm");
  if (form) {
    form.addEventListener("submit", async function (e) {
      e.preventDefault();

      const rawEl = el("raw_text");
      const raw = rawEl ? rawEl.value : "";

      if (!raw || raw.trim().length < 3) {
        showModal(
          tr("simple_error_title", "Ошибка"),
          tr("simple_error_need_more_text", "Введите более развернутое описание.")
        );
        return;
      }

      let r;
      try {
        r = await fetch("/api/simple/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ raw_text: raw })
        });
      } catch (e2) {
        showModal(
          tr("simple_error_title", "Ошибка"),
          tr("simple_error_network_analyze", "Ошибка сети при анализе.")
        );
        return;
      }

      let j;
      try {
        j = await r.json();
      } catch (e3) {
        showModal(
          tr("simple_error_title", "Ошибка"),
          tr("simple_error_bad_analyze_response", "Некорректный ответ сервера анализа.")
        );
        return;
      }

      if (!r.ok || j.error) {
        showModal(
          tr("simple_error_title", "Ошибка"),
          j.error || tr("simple_error_analyze_generic", "Ошибка анализа")
        );
        return;
      }

      currentAnalysis = j.analysis || null;
      currentDuplicateId = j.duplicate_id || null;
      currentDuplicateTitle = j.duplicate_title || null;

      // ✅ normalize similarity
      currentSimilarity = normalizeSimilarity(j.similarity || 0);

      renderPreviewFromAnalysis(currentAnalysis, currentSimilarity, currentDuplicateTitle);
      showBlock("simpleStepPreview");
    });
  }

  // ================= ANALYZE BUTTON FIX =================

  const btnAnalyze = el("btnAnalyze");
  if (btnAnalyze) {
    btnAnalyze.addEventListener("click", function () {
      const form = el("simpleForm");
      if (!form) return;

      // requestSubmit() is the most correct way (triggers submit handlers)
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      }
    });
  }

  // ================= PLACEHOLDER DUP BUTTONS =================

  const placeholderMsg = tr("simple_placeholder_next_version", "Будет доступно в следующей версии.");

  ["btnView", "btnImprove", "btnSeparate"].forEach(id => {
    const b = el(id);
    if (!b) return;
    b.addEventListener("click", function () {
      showModal("MindMesh", placeholderMsg);
    });
  });

  // ================= FALLBACK FILE =================

  function buildFallbackText() {
    const raw = el("raw_text") ? el("raw_text").value : "";
    const u = getUserFromDataset();

    const editEmail = el("edit_email") ? (el("edit_email").value || "") : "";
    const editName = el("edit_name") ? (el("edit_name").value || "") : "";

    const authorName = (editName || u.name || "Unknown").trim();
    const authorEmail = (editEmail || u.email || "Not provided").trim();

    const now = new Date().toLocaleString();

    const title = currentAnalysis?.title || "";
    const short = currentAnalysis?.short || "";
    const full = currentAnalysis?.full || "";
    const keywords = (currentAnalysis?.keywords || []).join(", ");

    const similarity = formatSimilarityPercent(currentSimilarity);
    const duplicate = currentDuplicateId || "None";

    return [
      mm_t("simple_fallback_file_header"),
      "--------------------------------",
      "",
      `${mm_t("simple_fallback_file_date")}: ${now}`,
      "",
      `${mm_t("assistant_label_author")}: ${authorName}`,
      `${mm_t("simple_label_email")}: ${authorEmail}`,
      "",
      `${mm_t("simple_fallback_status_not_saved")}`,
      "",
      `${mm_t("assistant_label_title")}:`,
      title,
      "",
      `${mm_t("assistant_label_short")}:`,
      short,
      "",
      `${mm_t("assistant_label_full")}:`,
      full,
      "",
      `${mm_t("assistant_label_keywords")}:`,
      keywords,
      "",
      `${mm_t("simple_fallback_file_similarity")}:`,
      `${similarity}`,
      "",
      `${mm_t("simple_fallback_file_duplicate")}:`,
      duplicate,
      "",
      "--------------------------------",
      `${mm_t("simple_fallback_file_raw")}:`,
      raw
    ].join("\n");
  }

  function showFallbackModal(reasonText) {
    const fallbackText = buildFallbackText();
    const reason = reasonText || "Server error";

    showModal(
      mm_t("simple_fallback_title"),
      mm_t("simple_fallback_message", { reason }),
      [
        {
          text: mm_t("simple_fallback_retry"),
          class: "btn primary",
          onClick: () => { el("btnSave")?.click(); }
        },
        {
          text: mm_t("simple_fallback_copy"),
          class: "btn secondary",
          onClick: async () => {
            try {
              await navigator.clipboard.writeText(fallbackText);
              showModal(mm_t("simple_fallback_title"), mm_t("simple_fallback_copied"));
            } catch (e) {
              showModal(mm_t("simple_fallback_title"), mm_t("simple_fallback_copy_error"));
            }
          }
        },
        {
          text: mm_t("simple_fallback_download"),
          class: "btn secondary",
          onClick: () => {
            const blob = new Blob([fallbackText], { type: "text/plain;charset=utf-8;" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "MindMesh_Idea_Backup.txt";
            a.click();
            URL.revokeObjectURL(url);
          }
        }
      ]
    );
  }

  // ================= SAVE (DB) =================

  async function saveToServer(payload) {
    try {
      const r = await fetch("/api/simple/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      let j = {};
      try { j = await r.json(); } catch (e) {}
      return { r, j };
    } catch (e) {
      return { r: null, j: {}, network_error: true, error_message: (e && e.message) ? e.message : "Network error" };
    }
  }

  // ================= Modal Email =================

function showEmailPromptAndSave() {
  const overlay = el("mmModalOverlay");
  const titleEl = el("mmModalTitle");
  const bodyEl = el("mmModalBody");
  const actionsEl = el("mmModalActions");

  if (!overlay || !titleEl || !bodyEl || !actionsEl) {
    console.error("Modal elements not found in DOM");
    return;
  }

  titleEl.innerText = tr("simple_email_prompt_title", "Введите данные");
  bodyEl.innerText = tr(
    "simple_email_prompt_text",
    "Чтобы сохранить идею, укажите email и имя. Пароль не обязателен."
  );

  actionsEl.innerHTML = "";

  // --- Prefill из edit / dataset ---
  const u = getUserFromDataset();
  const editEmail = el("edit_email") ? (el("edit_email").value || "").trim() : "";
  const editName = el("edit_name") ? (el("edit_name").value || "").trim() : "";

  const baseEmail = editEmail || (u.email || "").trim();

  let baseFirst = "";
  let baseLast = "";

  const baseName = editName || (u.name || "").trim();
  if (baseName) {
    const parts = baseName.split(/\s+/).filter(Boolean);
    baseFirst = parts[0] || "";
    baseLast = parts.slice(1).join(" ") || "";
  }

  // --- Inputs ---
  const inputEmail = document.createElement("input");
  inputEmail.type = "email";
  inputEmail.placeholder = tr("simple_email_prompt_email_ph", "email@example.com");
  inputEmail.value = baseEmail;
  inputEmail.style.width = "100%";
  inputEmail.style.boxSizing = "border-box";
  inputEmail.style.marginBottom = "10px";

  const inputFirst = document.createElement("input");
  inputFirst.type = "text";
  inputFirst.placeholder = tr("simple_email_prompt_first_ph", "Имя");
  inputFirst.value = pendingAuthorFirstName || baseFirst;
  inputFirst.style.width = "100%";
  inputFirst.style.boxSizing = "border-box";
  inputFirst.style.marginBottom = "10px";

  const inputLast = document.createElement("input");
  inputLast.type = "text";
  inputLast.placeholder = tr("simple_email_prompt_last_ph", "Фамилия");
  inputLast.value = pendingAuthorLastName || baseLast;
  inputLast.style.width = "100%";
  inputLast.style.boxSizing = "border-box";
  inputLast.style.marginBottom = "10px";

  actionsEl.appendChild(inputEmail);
  actionsEl.appendChild(inputFirst);
  actionsEl.appendChild(inputLast);

// --- Inline error box (UX-stable, multilingual safe) ---
  const errorBox = document.createElement("div");
  errorBox.style.color = "#c62828";
  errorBox.style.marginBottom = "10px";
  errorBox.style.fontSize = "0.9em";
  actionsEl.appendChild(errorBox);

  function setModalError(msgKey, fallback) {
  errorBox.innerText = tr(msgKey, fallback);
	}  

  const row = document.createElement("div");
  row.style.display = "flex";
  row.style.gap = "10px";

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "btn primary";
  saveBtn.innerText = tr("simple_email_prompt_save", "Сохранить");

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.className = "btn subtle";
  cancelBtn.innerText = tr("simple_email_prompt_cancel", "Отмена");

  cancelBtn.onclick = function () {
    overlay.style.display = "none";
  };

  saveBtn.onclick = async function () {
    const email = (inputEmail.value || "").trim();
    const first = (inputFirst.value || "").trim();
    const last = (inputLast.value || "").trim();

   setModalError("", "");

	if (!email) {
	setModalError("simple_error_email_required", "Email обязателен.");
	return;
	}

	if (!first) {
	setModalError("simple_error_name_required", "Имя обязательно.");
	return;
	}

    // сохраним введённое, чтобы не терялось при повторных попытках
    pendingAuthorEmail = email;
    pendingAuthorFirstName = first;
    pendingAuthorLastName = last;

    const displayName = (first + " " + last).trim();

    // Обновим edit поля, чтобы Preview показывал автора
    if (el("edit_email")) el("edit_email").value = email;
    if (el("edit_name")) el("edit_name").value = displayName;

    const raw = el("raw_text") ? (el("raw_text").value || "") : "";

    const { r, j } = await saveToServer({
      analysis: currentAnalysis,
      raw_text: raw,
      duplicate_id: currentDuplicateId,
      similarity: currentSimilarity,
      name: displayName,      // важно: сервер уже умеет принимать name
      email: email,
      first_name: first,      // доп. поля — сервер может игнорировать, не мешают
      last_name: last
    });

    if (!r) {
	setModalError("simple_error_network", "Ошибка сети.");
	return;
	}

	if (!r.ok) {
	const msg = j?.message || j?.error || "Ошибка сервера";
	errorBox.innerText = msg; // серверное сообщение как есть
	return;
	}

// Закрываем ТОЛЬКО при успехе
overlay.style.display = "none";

    showModal(tr("simple_success_title", "Готово"), tr("simple_saved_ok", "Идея сохранена. ID: ") + (j.idea_id || "(no id)"));
  };
// =================                 =================/
  row.appendChild(saveBtn);
  row.appendChild(cancelBtn);
  actionsEl.appendChild(row);

  overlay.style.display = "flex";
  setTimeout(() => {
    if (!inputEmail.value) inputEmail.focus();
    else if (!inputFirst.value) inputFirst.focus();
    else inputLast.focus();
  }, 50);
}

// ================= RE-ANALYZE AFTER EDIT =================

async function reanalyzeCurrent() {

  if (!currentAnalysis) return;

  const raw = el("raw_text") ? (el("raw_text").value || "") : "";

  // Берём обновлённый full (он уже изменён через applyEditFormToCurrent)
  const textForAnalyze =
    currentAnalysis.full ||
    currentAnalysis.short ||
    raw;

  try {
    const r = await fetch("/api/simple/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_text: textForAnalyze })
    });

    const j = await r.json();

    if (!r.ok || j.error) {
      console.warn("Re-analyze failed, keeping previous analysis");
      return;
    }

    // Обновляем данные анализа
    currentDuplicateId = j.duplicate_id || null;
    currentDuplicateTitle = j.duplicate_title || null;
    currentSimilarity = normalizeSimilarity(j.similarity || 0);

  } catch (e) {
    console.warn("Re-analyze network error", e);
  }
}

  // ================= EDIT FLOW =================

  function fillEditFormFromCurrent() {
    if (!currentAnalysis) return;

    el("edit_title").value = currentAnalysis.title || "";
    el("edit_short").value = currentAnalysis.short || "";

    // full: если нет, подставим исходный raw_text
    const raw = (el("raw_text") && el("raw_text").value) ? el("raw_text").value : "";
    el("edit_full").value = currentAnalysis.full || currentAnalysis.short || raw || "";

    el("edit_keywords").value = (currentAnalysis.keywords || []).join(", ");

    // имя/почта: из user dataset, если залогинен
    const u = getUserFromDataset();
    if (el("edit_name")) el("edit_name").value = u.name || "";
    if (el("edit_email")) el("edit_email").value = u.email || "";
  }

  function applyEditFormToCurrent() {
    if (!currentAnalysis) return;

    currentAnalysis.title = (el("edit_title").value || "").trim();
    currentAnalysis.short = (el("edit_short").value || "").trim();
    currentAnalysis.full = (el("edit_full").value || "").trim();

    const kwRaw = (el("edit_keywords").value || "").trim();
    currentAnalysis.keywords = kwRaw
      ? kwRaw.split(",").map(x => x.trim()).filter(Boolean).slice(0, 10)
      : [];
  }

  const btnEdit = el("btnEdit");
  if (btnEdit) {
    btnEdit.addEventListener("click", function () {
      if (!currentAnalysis) {
        showModal(
          tr("simple_error_title", "Ошибка"),
          tr("simple_error_press_analyze", "Сначала нажмите «Проанализировать».")
        );
        return;
      }
      fillEditFormFromCurrent();
      showBlock("simpleStepEdit");
    });
  }

const btnSaveEdited = el("btnSaveEdited");
if (btnSaveEdited) {
  btnSaveEdited.addEventListener("click", async function () {

    if (!currentAnalysis) {
      showModal(
        tr("simple_error_title", "Ошибка"),
        tr("simple_error_no_analysis", "Нет данных анализа.")
      );
      return;
    }

    applyEditFormToCurrent();

    // 🔄 повторный анализ
    await reanalyzeCurrent();

    renderPreviewFromAnalysis(
      currentAnalysis,
      currentSimilarity,
      currentDuplicateTitle
    );

    showBlock("simpleStepPreview");
  });

  }

// ================= SAVE (DB BUTTON) =================

const btnSave = el("btnSave");
if (btnSave) {
  btnSave.addEventListener("click", async function () {

    if (!currentAnalysis) {
      showModal(
        tr("simple_error_title", "Ошибка"),
        tr("simple_error_press_analyze", "Сначала нажмите «Проанализировать».")
      );
      return;
    }

    const raw = el("raw_text") ? (el("raw_text").value || "") : "";
    const editName = el("edit_name") ? (el("edit_name").value || "") : "";
    const editEmail = el("edit_email") ? (el("edit_email").value || "") : "";

    const finalName =
      editName ||
      ((pendingAuthorFirstName || "") + " " + (pendingAuthorLastName || "")).trim();

    const finalEmail =
      editEmail ||
      pendingAuthorEmail ||
      "";

    const { r, j } = await saveToServer({
      analysis: currentAnalysis,
      raw_text: raw,
      duplicate_id: currentDuplicateId,
      similarity: currentSimilarity,
      name: finalName,
      email: finalEmail
    });

    if (!r) {
      showFallbackModal("Network error");
      return;
    }

    // сервер просит email
    if (r.status === 401 || j.status === "need_email") {
      showEmailPromptAndSave();
      return;
    }

    if (!r.ok) {
      showFallbackModal(j.message || j.error || "Ошибка сервера");
      return;
    }

    showModal(
      tr("simple_success_title", "Успешно"),
      tr("simple_success_saved_id", "Идея сохранена. ID: ") + (j.idea_id || "(no id)")
    );
  });
}

  // ================= NEW / CANCEL =================

  const btnNew = el("btnNew");
  if (btnNew) {
    btnNew.addEventListener("click", function () {
      location.reload();
    });
  }

  const btnCancel = el("btnCancel");
  if (btnCancel) {
    btnCancel.addEventListener("click", function () {
      location.reload();
    });
  }

  // ================= LocalID =================

  function generateLocalID() {
    const now = new Date();
    const pad = n => String(n).padStart(2, '0');
    const y = now.getFullYear();
    const m = pad(now.getMonth() + 1);
    const d = pad(now.getDate());
    const h = pad(now.getHours());
    const min = pad(now.getMinutes());
    const s = pad(now.getSeconds());
    return `MM-LocalTemp-${y}${m}${d}-${h}${min}${s}`;
  }

  // ================= Error klass =================

  function classifyError(response, json) {

    if (!navigator.onLine) {
      return {
        code: "NO_NETWORK",
        message: tr("error_no_network", "Нет сети. Проверь интернет."),
        serverComponent: "Unknown"
      };
    }

    if (!response) {
      return {
        code: "NO_NETWORK",
        message: tr("error_no_network", "Нет сети. Проверь интернет."),
        serverComponent: "Unknown"
      };
    }

    if (response.status >= 500) {
      return {
        code: "SERVER_ERROR",
        message: tr("error_server_unavailable", "Сервер временно недоступен."),
        serverComponent: "API"
      };
    }

    if (response.status === 400 || response.status === 422) {
      return {
        code: "DATABASE_ERROR",
        message: tr("error_database", "Ошибка базы данных."),
        serverComponent: "Airtable"
      };
    }

    return {
      code: "UNKNOWN_ERROR",
      message: tr("error_internal", "Внутренняя ошибка."),
      serverComponent: "Unknown"
    };
  }

});