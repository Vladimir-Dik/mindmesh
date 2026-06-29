/*
============================================================
Project: MindMesh
File: advanced.js
Version: 4.0
Date: 23.04.2026
Purpose:
- Advanced Mode (продвинутый режим) client logic
- Modular workdesk state management
- Draft editor, assistant session, AI module rendering
- Prepared for /api/advanced/start, /api/advanced/message, /api/advanced/confirm
============================================================
*/

(function () {
  "use strict";

  // ============================================================
  // CONFIG
  // ============================================================
  const API = {
    start: "/api/advanced/start",
    message: "/api/advanced/message",
    confirm: "/api/advanced/confirm",
    similarity: "/api/advanced/similarity"
  };

  // ============================================================
  // STATE
  // ============================================================
  const advancedState = {
    sessionId: null,
    started: false,
    waiting: false,
    draftDirty: false,

    draft: {
      title: "",
      short_description: "",
      full_description: "",
      keywords: "",
      category: "",
      region: "",
      language_original: "",
      readiness_level: "",
      patentability: "",
      confidentiality_level: "",
      external_links: "",
      notes: ""
    },

    ai: {
      assistantMessages: [],
      structureSummary: "",
      analysisSummary: "",
      similaritySummary: "",
      recommendationsSummary: "",
      notesAI: "",
      uniquenessValue: "—",
      uniquenessText: "",
      riskValue: "—",
      riskText: "",
      missingFields: [],
      relatedIdeas: [],
      duplicateWarning: "",
      reviewNote: "",
      sessionState: "idle",
      reviewState: "ready",
      moduleStates: {
        structuring: "idle",
        analysis: "idle",
        similarity: "idle",
        recommendations: "idle"
      }
    }
  };

  // ============================================================
  // DOM
  // ============================================================
  const dom = {};

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    bindDom();
    if (!dom.shell) return;

    bindEvents();
    collectDraftFromForm();
    renderAll();
    startSession();
  }

  function bindDom() {
    dom.shell = document.getElementById("advancedShell");

    dom.form = document.getElementById("advancedDraftForm");

    dom.title = document.getElementById("advancedTitle");
    dom.shortDescription = document.getElementById("advancedShortDescription");
    dom.fullDescription = document.getElementById("advancedFullDescription");
    dom.keywords = document.getElementById("advancedKeywords");
    dom.category = document.getElementById("advancedCategory");
    dom.region = document.getElementById("advancedRegion");
    dom.language = document.getElementById("advancedLanguage");
    dom.readiness = document.getElementById("advancedReadiness");
    dom.patentability = document.getElementById("advancedPatentability");
    dom.confidentiality = document.getElementById("advancedConfidentiality");
    dom.externalLinks = document.getElementById("advancedExternalLinks");
    dom.notes = document.getElementById("advancedNotes");

    dom.backBtn = document.getElementById("advancedBackBtn");
    dom.newSessionBtn = document.getElementById("advancedNewSessionBtn");
    dom.saveDraftBtn = document.getElementById("advancedSaveDraftBtn");
    dom.saveIdeaBtn = document.getElementById("advancedSaveIdeaBtn");
    dom.clearDraftBtn = document.getElementById("advancedClearDraftBtn");
    dom.runAnalysisBtn = document.getElementById("advancedRunAnalysisBtn");
    dom.checkSimilarityBtn = document.getElementById("advancedCheckSimilarityBtn");
    dom.refreshBtn = document.getElementById("advancedRefreshBtn");
    dom.sendToReviewBtn = document.getElementById("advancedSendToReviewBtn");
    dom.continueBtn = document.getElementById("advancedContinueBtn");

    dom.chat = document.getElementById("advancedChat");
    dom.assistantEmpty = document.getElementById("advancedAssistantEmpty");
    dom.composer = document.getElementById("advancedComposer");
    dom.messageInput = document.getElementById("advancedMsg");
    dom.sendBtn = document.getElementById("advancedSendBtn");

    dom.modeBadge = document.getElementById("advancedModeBadge");
    dom.sessionState = document.getElementById("advancedSessionState");
    dom.reviewState = document.getElementById("advancedReviewState");
    dom.workspaceStatus = document.getElementById("workspaceStatus");
    dom.assistantState = document.getElementById("assistantState");
    dom.reviewPanelState = document.getElementById("reviewPanelState");
    dom.draftDirtyState = document.getElementById("draftDirtyState");

    dom.moduleStructuringState = document.getElementById("moduleStructuringState");
    dom.moduleAnalysisState = document.getElementById("moduleAnalysisState");
    dom.moduleSimilarityState = document.getElementById("moduleSimilarityState");
    dom.moduleRecommendationsState = document.getElementById("moduleRecommendationsState");

    dom.structureSummary = document.getElementById("advancedStructureSummary");
    dom.analysisSummary = document.getElementById("advancedAnalysisSummary");
    dom.similaritySummary = document.getElementById("advancedSimilaritySummary");
    dom.recommendationsSummary = document.getElementById("advancedRecommendationsSummary");

    dom.uniquenessValue = document.getElementById("advancedUniquenessValue");
    dom.uniquenessText = document.getElementById("advancedUniquenessText");
    dom.riskValue = document.getElementById("advancedRiskValue");
    dom.riskText = document.getElementById("advancedRiskText");
    dom.notesAI = document.getElementById("advancedNotesAI");
    dom.missingFieldsList = document.getElementById("advancedMissingFieldsList");
    dom.relatedIdeas = document.getElementById("advancedRelatedIdeas");
    dom.duplicateWarning = document.getElementById("advancedDuplicateWarning");
    dom.reviewNote = document.getElementById("advancedReviewNote");
  }

  function bindEvents() {
    const draftInputs = [
      dom.title,
      dom.shortDescription,
      dom.fullDescription,
      dom.keywords,
      dom.category,
      dom.region,
      dom.language,
      dom.readiness,
      dom.patentability,
      dom.confidentiality,
      dom.externalLinks,
      dom.notes
    ];

    draftInputs.forEach((input) => {
      if (!input) return;
      input.addEventListener("input", onDraftInput);
      input.addEventListener("change", onDraftInput);
    });

    if (dom.sendBtn) {
      dom.sendBtn.addEventListener("click", onSendMessage);
    }

    if (dom.messageInput) {
      dom.messageInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          onSendMessage();
        }
      });
    }

    if (dom.runAnalysisBtn) {
      dom.runAnalysisBtn.addEventListener("click", onRunAnalysis);
    }

    if (dom.checkSimilarityBtn) {
      dom.checkSimilarityBtn.addEventListener("click", onCheckSimilarity);
    }

    if (dom.saveIdeaBtn) {
      dom.saveIdeaBtn.addEventListener("click", onSaveIdea);
    }

    if (dom.saveDraftBtn) {
      dom.saveDraftBtn.addEventListener("click", onSaveDraftLocal);
    }

    if (dom.clearDraftBtn) {
      dom.clearDraftBtn.addEventListener("click", onClearDraft);
    }

    if (dom.newSessionBtn) {
      dom.newSessionBtn.addEventListener("click", onNewSession);
    }

    if (dom.backBtn) {
      dom.backBtn.addEventListener("click", function () {
        window.history.back();
      });
    }

    if (dom.refreshBtn) {
      dom.refreshBtn.addEventListener("click", function () {
        renderAll();
      });
    }

    if (dom.continueBtn) {
      dom.continueBtn.addEventListener("click", function () {
        focusPrimaryInput();
      });
    }

    if (dom.sendToReviewBtn) {
      dom.sendToReviewBtn.addEventListener("click", onSendToReview);
    }
  }

  // ============================================================
  // I18N
  // ============================================================
  function tr(key, fallback) {
    try {
      if (typeof window.tr === "function") {
        return window.tr(key, fallback);
      }
      if (typeof window.translate === "function") {
        return window.translate(key, fallback);
      }
      if (typeof window.i18n === "object" && window.i18n && window.i18n[key]) {
        return window.i18n[key];
      }
    } catch (_) {}
    return fallback || key;
  }

  // ============================================================
  // STATE HELPERS
  // ============================================================
  function collectDraftFromForm() {
    advancedState.draft.title = readValue(dom.title);
    advancedState.draft.short_description = readValue(dom.shortDescription);
    advancedState.draft.full_description = readValue(dom.fullDescription);
    advancedState.draft.keywords = readValue(dom.keywords);
    advancedState.draft.category = readValue(dom.category);
    advancedState.draft.region = readValue(dom.region);
    advancedState.draft.language_original = readValue(dom.language);
    advancedState.draft.readiness_level = readValue(dom.readiness);
    advancedState.draft.patentability = readValue(dom.patentability);
    advancedState.draft.confidentiality_level = readValue(dom.confidentiality);
    advancedState.draft.external_links = readValue(dom.externalLinks);
    advancedState.draft.notes = readValue(dom.notes);
  }

  function applyDraftToForm() {
    writeValue(dom.title, advancedState.draft.title);
    writeValue(dom.shortDescription, advancedState.draft.short_description);
    writeValue(dom.fullDescription, advancedState.draft.full_description);
    writeValue(dom.keywords, advancedState.draft.keywords);
    writeValue(dom.category, advancedState.draft.category);
    writeValue(dom.region, advancedState.draft.region);
    writeValue(dom.language, advancedState.draft.language_original);
    writeValue(dom.readiness, advancedState.draft.readiness_level);
    writeValue(dom.patentability, advancedState.draft.patentability);
    writeValue(dom.confidentiality, advancedState.draft.confidentiality_level);
    writeValue(dom.externalLinks, advancedState.draft.external_links);
    writeValue(dom.notes, advancedState.draft.notes);
  }

  function readValue(node) {
    return node ? String(node.value || "").trim() : "";
  }

  function writeValue(node, value) {
    if (node) node.value = value || "";
  }

  function setWaiting(flag) {
    advancedState.waiting = !!flag;
    renderButtons();
    renderStatusLine();
  }

  function setDraftDirty(flag) {
    advancedState.draftDirty = !!flag;
    renderStatusLine();
  }

  function hasMeaningfulDraft() {
    const d = advancedState.draft;
    return Boolean(
      d.title ||
      d.short_description ||
      d.full_description ||
      d.keywords ||
      d.category ||
      d.region ||
      d.language_original ||
      d.readiness_level ||
      d.patentability ||
      d.confidentiality_level ||
      d.external_links ||
      d.notes
    );
  }

  function focusPrimaryInput() {
    if (!readValue(dom.fullDescription)) {
      dom.fullDescription?.focus();
      return;
    }
    dom.messageInput?.focus();
  }

  function resetDraft() {
    advancedState.draft = {
      title: "",
      short_description: "",
      full_description: "",
      keywords: "",
      category: "",
      region: "",
      language_original: "",
      readiness_level: "",
      patentability: "",
      confidentiality_level: "",
      external_links: "",
      notes: ""
    };
    applyDraftToForm();
    setDraftDirty(false);
  }

  function resetAIState() {
    advancedState.ai = {
      assistantMessages: [],
      structureSummary: "",
      analysisSummary: "",
      similaritySummary: "",
      recommendationsSummary: "",
      notesAI: "",
      uniquenessValue: "—",
      uniquenessText: "",
      riskValue: "—",
      riskText: "",
      missingFields: [],
      relatedIdeas: [],
      duplicateWarning: "",
      reviewNote: "",
      sessionState: "idle",
      reviewState: "ready",
      moduleStates: {
        structuring: "idle",
        analysis: "idle",
        similarity: "idle",
        recommendations: "idle"
      }
    };
  }

  // ============================================================
  // RENDER
  // ============================================================
  function renderAll() {
    renderStatusLine();
    renderButtons();
    renderAssistant();
    renderModules();
    renderResults();
  }

  function renderStatusLine() {
    setChipText(dom.sessionState, advancedState.ai.sessionState);
    setChipText(dom.workspaceStatus, advancedState.waiting ? "processing" : advancedState.ai.sessionState);
    setChipText(dom.assistantState, advancedState.waiting ? "processing" : advancedState.ai.sessionState);
    setChipText(dom.reviewState, advancedState.ai.reviewState);
    setChipText(dom.reviewPanelState, advancedState.ai.reviewState);
    setChipText(dom.draftDirtyState, advancedState.draftDirty ? "active" : "idle");

    setChipText(dom.moduleStructuringState, advancedState.ai.moduleStates.structuring);
    setChipText(dom.moduleAnalysisState, advancedState.ai.moduleStates.analysis);
    setChipText(dom.moduleSimilarityState, advancedState.ai.moduleStates.similarity);
    setChipText(dom.moduleRecommendationsState, advancedState.ai.moduleStates.recommendations);
  }

  function renderButtons() {
    const disabled = advancedState.waiting;

    setDisabled(dom.sendBtn, disabled);
    setDisabled(dom.runAnalysisBtn, disabled);
    setDisabled(dom.checkSimilarityBtn, disabled);
    setDisabled(dom.saveIdeaBtn, disabled || !hasMeaningfulDraft());
    setDisabled(dom.saveDraftBtn, disabled || !hasMeaningfulDraft());
    setDisabled(dom.clearDraftBtn, disabled || !hasMeaningfulDraft());
    setDisabled(dom.newSessionBtn, disabled);
    setDisabled(dom.refreshBtn, disabled);
    setDisabled(dom.sendToReviewBtn, disabled || !hasMeaningfulDraft());
    setDisabled(dom.continueBtn, disabled);

    if (dom.sendBtn) {
      dom.sendBtn.textContent = advancedState.waiting
        ? tr("status_processing", "Processing")
        : tr("advanced_send_btn", "Send");
    }

    if (dom.runAnalysisBtn) {
      dom.runAnalysisBtn.textContent = advancedState.waiting
        ? tr("status_processing", "Processing")
        : tr("action_run_analysis", "Run Analysis");
    }
  }

  function renderAssistant() {
    if (!dom.chat || !dom.assistantEmpty) return;

    dom.chat.innerHTML = "";

    const items = advancedState.ai.assistantMessages || [];
    const hasMessages = items.length > 0;

    dom.assistantEmpty.style.display = hasMessages ? "none" : "";
    dom.chat.style.display = hasMessages ? "" : "none";

    items.forEach((item) => {
      const bubble = document.createElement("div");
      bubble.className = "advanced-message advanced-message--" + (item.role || "assistant");

      const role = document.createElement("div");
      role.className = "advanced-message__role";
      role.textContent =
        item.role === "user"
          ? tr("common_you", "You")
          : tr("common_ai", "AI");

      const text = document.createElement("div");
      text.className = "advanced-message__text";
      text.innerHTML = formatText(item.content || "");

      bubble.appendChild(role);
      bubble.appendChild(text);
      dom.chat.appendChild(bubble);
    });

    dom.chat.scrollTop = dom.chat.scrollHeight;
  }

  function renderModules() {
    setHTMLOrPlaceholder(
      dom.structureSummary,
      advancedState.ai.structureSummary,
      tr("advanced_draft_empty", "No structured draft yet.")
    );

    setHTMLOrPlaceholder(
      dom.analysisSummary,
      advancedState.ai.analysisSummary,
      tr("advanced_ai_waiting", "Waiting for analysis.")
    );

    setHTMLOrPlaceholder(
      dom.similaritySummary,
      advancedState.ai.similaritySummary,
      tr("advanced_similarity_empty", "Similarity results will appear here.")
    );

    setHTMLOrPlaceholder(
      dom.recommendationsSummary,
      advancedState.ai.recommendationsSummary,
      tr("advanced_next_steps", "Next steps will appear here.")
    );
  }

  function renderResults() {
    if (dom.uniquenessValue) {
      dom.uniquenessValue.textContent = advancedState.ai.uniquenessValue || "—";
    }
    if (dom.uniquenessText) {
      dom.uniquenessText.textContent =
        advancedState.ai.uniquenessText || tr("advanced_similarity_empty", "Similarity results will appear here.");
    }

    if (dom.riskValue) {
      dom.riskValue.textContent = advancedState.ai.riskValue || "—";
    }
    if (dom.riskText) {
      dom.riskText.textContent =
        advancedState.ai.riskText || tr("advanced_ai_waiting", "Waiting for analysis.");
    }

    if (dom.notesAI) {
      dom.notesAI.innerHTML = formatText(
        advancedState.ai.notesAI || tr("advanced_ai_waiting", "Waiting for analysis.")
      );
    }

    if (dom.missingFieldsList) {
      dom.missingFieldsList.innerHTML = "";
      const fields = Array.isArray(advancedState.ai.missingFields) ? advancedState.ai.missingFields : [];

      if (!fields.length) {
        const li = document.createElement("li");
        li.textContent = tr("status_ready", "Ready");
        dom.missingFieldsList.appendChild(li);
      } else {
        fields.forEach((field) => {
          const li = document.createElement("li");
          li.textContent = prettifyFieldName(field);
          dom.missingFieldsList.appendChild(li);
        });
      }
    }

    if (dom.relatedIdeas) {
      const related = Array.isArray(advancedState.ai.relatedIdeas) ? advancedState.ai.relatedIdeas : [];
      if (!related.length) {
        dom.relatedIdeas.textContent = tr("advanced_similarity_empty", "Similarity results will appear here.");
      } else {
        dom.relatedIdeas.innerHTML = related
          .map((item) => {
            const title = escapeHtml(item.title || item.idea_title || tr("common_idea", "Idea"));
            const score = item.score != null ? ` (${item.score}%)` : "";
            return `<div class="advanced-related-item">${title}${score}</div>`;
          })
          .join("");
      }
    }

    if (dom.duplicateWarning) {
      dom.duplicateWarning.textContent =
        advancedState.ai.duplicateWarning || tr("status_ready", "Ready");
    }

    if (dom.reviewNote) {
      dom.reviewNote.textContent =
        advancedState.ai.reviewNote || tr(
          "advanced_intro_text",
          "Fill the draft or send a message so AI can begin structuring the idea."
        );
    }
  }

  function setChipText(node, stateKey) {
    if (!node) return;

    const key = mapStatusKey(stateKey);
    node.textContent = tr(key, fallbackStatus(stateKey));

    node.classList.remove(
      "mini-chip--soft",
      "mini-chip--blue",
      "mini-chip--green",
      "mini-chip--warn",
      "mini-chip--danger",
      "status-chip--violet",
      "status-chip--blue",
      "status-chip--green",
      "status-chip--warn",
      "status-chip--danger"
    );

    const variant = statusVariant(stateKey);

    if (node.classList.contains("status-chip")) {
      node.classList.add("status-chip--" + variant);
    } else {
      node.classList.add("mini-chip--" + variant);
    }
  }

  function mapStatusKey(stateKey) {
    switch ((stateKey || "").toLowerCase()) {
      case "idle":
        return "status_idle";
      case "active":
        return "status_active";
      case "ready":
        return "status_ready";
      case "processing":
      case "working":
        return "status_processing";
      case "completed":
      case "done":
        return "status_completed";
      case "review":
      case "pending_review":
        return "status_review";
      case "warning":
      case "warn":
        return "status_warning";
      case "blocked":
      case "error":
        return "status_blocked";
      default:
        return "status_idle";
    }
  }

  function fallbackStatus(stateKey) {
    switch ((stateKey || "").toLowerCase()) {
      case "idle":
        return "Idle";
      case "active":
        return "Active";
      case "ready":
        return "Ready";
      case "processing":
      case "working":
        return "Processing";
      case "completed":
      case "done":
        return "Completed";
      case "review":
      case "pending_review":
        return "Review";
      case "warning":
      case "warn":
        return "Warning";
      case "blocked":
      case "error":
        return "Blocked";
      default:
        return "Idle";
    }
  }

  function statusVariant(stateKey) {
    switch ((stateKey || "").toLowerCase()) {
      case "active":
        return "violet";
      case "ready":
      case "completed":
      case "done":
        return "green";
      case "processing":
      case "working":
      case "review":
      case "pending_review":
        return "blue";
      case "warning":
      case "warn":
        return "warn";
      case "blocked":
      case "error":
        return "danger";
      case "idle":
      default:
        return "soft";
    }
  }

  function setHTMLOrPlaceholder(node, html, placeholder) {
    if (!node) return;
    if (html && String(html).trim()) {
      node.innerHTML = html;
    } else {
      node.textContent = placeholder;
    }
  }

  function setDisabled(node, value) {
    if (node) node.disabled = !!value;
  }

  // ============================================================
  // EVENTS
  // ============================================================
  function onDraftInput() {
    collectDraftFromForm();
    setDraftDirty(true);
    updateMissingFieldsLocal();
    renderAll();
  }

  async function onSendMessage() {
    const message = readValue(dom.messageInput);
    collectDraftFromForm();

    if (!message) {
      notify(tr("advanced_input_placeholder", "Describe your idea or answer AI questions"));
      dom.messageInput?.focus();
      return;
    }

    if (!advancedState.started) {
      await startSession();
    }

    pushMessage("user", message);
    writeValue(dom.messageInput, "");

    advancedState.ai.sessionState = "processing";
    advancedState.ai.moduleStates.structuring = "processing";
    advancedState.ai.moduleStates.analysis = "processing";
    setWaiting(true);
    renderAll();

    try {
      const payload = {
        session_id: advancedState.sessionId,
        message: message,
        draft: advancedState.draft,
        mode: "advanced",
        version: "4.0"
      };

      const result = await postJson(API.message, payload);
      applyAIResponse(result, { source: "message" });
    } catch (error) {
      console.error(error);
      advancedState.ai.sessionState = "warning";
      advancedState.ai.reviewNote = error.message || tr("common_error", "Error");
      pushMessage("assistant", tr("common_server_error", "Server error. Please try again."));
    } finally {
      setWaiting(false);
      renderAll();
    }
  }

  async function onRunAnalysis() {
    collectDraftFromForm();

    if (!hasMeaningfulDraft()) {
      notify(tr("advanced_intro_text", "Fill the draft or send a message so AI can begin structuring the idea."));
      focusPrimaryInput();
      return;
    }

    const syntheticMessage = buildDraftSummaryMessage();
    if (syntheticMessage) {
      writeValue(dom.messageInput, syntheticMessage);
      await onSendMessage();
    }
  }

  async function onCheckSimilarity() {
    collectDraftFromForm();

    if (!hasMeaningfulDraft()) {
      notify(tr("advanced_similarity_empty", "Similarity results will appear here."));
      return;
    }

    advancedState.ai.moduleStates.similarity = "processing";
    advancedState.ai.sessionState = "processing";
    setWaiting(true);
    renderAll();

    try {
      let result;

      try {
        result = await postJson(API.similarity, {
          session_id: advancedState.sessionId,
          draft: advancedState.draft,
          mode: "advanced",
          version: "4.0"
        });
      } catch (_) {
        result = buildLocalSimilarityFallback();
      }

      applySimilarityResult(result);
    } catch (error) {
      console.error(error);
      advancedState.ai.moduleStates.similarity = "warning";
      advancedState.ai.similaritySummary = tr("common_server_error", "Server error. Please try again.");
      advancedState.ai.duplicateWarning = tr("advanced_review_blocked_duplicate", "Saving can be paused if a strong overlap is detected.");
    } finally {
      setWaiting(false);
      renderAll();
    }
  }

  function onSaveDraftLocal() {
    collectDraftFromForm();

    if (!hasMeaningfulDraft()) {
      notify(tr("advanced_draft_empty", "No structured draft yet."));
      return;
    }

    try {
      const data = {
        saved_at: new Date().toISOString(),
        version: "4.0",
        mode: "advanced",
        session_id: advancedState.sessionId,
        draft: advancedState.draft,
        ai: advancedState.ai
      };

      localStorage.setItem("mindmesh_advanced_draft", JSON.stringify(data));
      setDraftDirty(false);
      advancedState.ai.reviewNote = tr("action_save_draft", "Save Draft");
      notify(tr("action_save_draft", "Save Draft"));
      renderAll();
    } catch (error) {
      console.error(error);
      notify(tr("common_server_error", "Server error. Please try again."));
    }
  }

  async function onSaveIdea() {
    collectDraftFromForm();

    if (!hasMeaningfulDraft()) {
      notify(tr("advanced_intro_text", "Fill the draft or send a message so AI can begin structuring the idea."));
      return;
    }

    if (
      advancedState.ai.duplicateWarning &&
      /strong|duplicate|совпад|overlap|blocked/i.test(advancedState.ai.duplicateWarning)
    ) {
      const proceed = window.confirm(
        tr(
          "advanced_review_blocked_duplicate",
          "Saving can be paused if a strong overlap is detected."
        )
      );
      if (!proceed) return;
    }

    advancedState.ai.sessionState = "processing";
    advancedState.ai.reviewState = "processing";
    setWaiting(true);
    renderAll();

    try {
      const payload = {
        session_id: advancedState.sessionId,
        draft: advancedState.draft,
        mode: "advanced",
        version: "4.0",
        ai_review_status: "pending"
      };

      const result = await postJson(API.confirm, payload);

      advancedState.ai.reviewState = "completed";
      advancedState.ai.sessionState = "completed";
      advancedState.ai.reviewNote =
        result.message ||
        tr("action_save_idea", "Save Idea");

      pushMessage(
        "assistant",
        result.assistant_reply ||
          tr("common_saved_successfully", "Saved successfully.")
      );

      setDraftDirty(false);
      renderAll();

      window.alert(
        result.message ||
          (tr("action_save_idea", "Save Idea") +
            (result.idea_id ? `: ${result.idea_id}` : ""))
      );
    } catch (error) {
      console.error(error);
      advancedState.ai.reviewState = "warning";
      advancedState.ai.sessionState = "warning";
      advancedState.ai.reviewNote = error.message || tr("common_server_error", "Server error. Please try again.");
      renderAll();
      window.alert(error.message || tr("common_server_error", "Server error. Please try again."));
    } finally {
      setWaiting(false);
      renderAll();
    }
  }

  function onClearDraft() {
    const ok = window.confirm(
      tr("advanced_clear_btn", "Clear")
    );
    if (!ok) return;

    resetDraft();
    resetAIState();
    writeValue(dom.messageInput, "");
    renderAll();
    focusPrimaryInput();
  }

  async function onNewSession() {
    const ok = window.confirm(
      tr("advanced_new_session_btn", "New Session")
    );
    if (!ok) return;

    resetDraft();
    resetAIState();
    writeValue(dom.messageInput, "");
    renderAll();
    await startSession(true);
  }

  function onSendToReview() {
    advancedState.ai.reviewState = "review";
    advancedState.ai.reviewNote = tr("action_send_to_review", "Send to Review");
    renderAll();
    notify(tr("action_send_to_review", "Send to Review"));
  }

  // ============================================================
  // START / SESSION
  // ============================================================
  async function startSession(forceNew = false) {
    setWaiting(true);
    advancedState.ai.sessionState = "processing";
    renderAll();

    try {
      const bootstrapNode = document.getElementById("advancedBootstrap");
      let bootstrap = { mode: "advanced", version: "4.0" };

      if (bootstrapNode?.textContent) {
        try {
          bootstrap = JSON.parse(bootstrapNode.textContent);
        } catch (_) {}
      }

      let result;
      try {
        result = await postJson(API.start, {
          force_new: !!forceNew,
          mode: bootstrap.mode || "advanced",
          version: bootstrap.version || "4.0"
        });
      } catch (_) {
        result = buildStartFallback();
      }

      advancedState.sessionId = result.session_id || generateSessionId();
      advancedState.started = true;
      advancedState.ai.sessionState = "active";
      advancedState.ai.reviewState = "ready";

      if (result.draft && typeof result.draft === "object") {
        advancedState.draft = {
          ...advancedState.draft,
          ...normalizeDraftPatch(result.draft)
        };
        applyDraftToForm();
      }

      const greeting =
        result?.assistant?.message ||
        tr("advanced_intro_text", "Fill the draft or send a message so AI can begin structuring the idea.");

      if (!advancedState.ai.assistantMessages.length) {
        pushMessage("assistant", greeting);
      }
    } catch (error) {
      console.error(error);
      advancedState.sessionId = generateSessionId();
      advancedState.started = true;
      advancedState.ai.sessionState = "warning";
      pushMessage("assistant", tr("common_server_error", "Server error. Please try again."));
    } finally {
      setWaiting(false);
      renderAll();
    }
  }

  // ============================================================
  // APPLY RESPONSES
  // ============================================================
  function applyAIResponse(result, options = {}) {
    if (!result || typeof result !== "object") {
      throw new Error(tr("common_server_error", "Server error. Please try again."));
    }

    if (result.session_id) {
      advancedState.sessionId = result.session_id;
    }

    if (result.assistant_reply) {
      pushMessage("assistant", result.assistant_reply);
    }

    if (result.draft_patch && typeof result.draft_patch === "object") {
      applyDraftPatch(result.draft_patch);
    }

    if (Array.isArray(result.missing_fields)) {
      advancedState.ai.missingFields = result.missing_fields;
    } else {
      updateMissingFieldsLocal();
    }

    if (Array.isArray(result.questions) && result.questions.length) {
      advancedState.ai.reviewNote = result.questions.join(" ");
    }

    if (result.module_results && typeof result.module_results === "object") {
      const mr = result.module_results;

      if (mr.structuring) {
        advancedState.ai.moduleStates.structuring = "completed";
        advancedState.ai.structureSummary = renderStructuringModule(mr.structuring);
      }

      if (mr.analysis) {
        advancedState.ai.moduleStates.analysis = "completed";
        advancedState.ai.analysisSummary = renderAnalysisModule(mr.analysis);
        advancedState.ai.notesAI = mr.analysis.notes_ai || mr.analysis.summary || "";
        advancedState.ai.riskValue = mr.analysis.risk_level || "—";
        advancedState.ai.riskText = mr.analysis.risk_text || mr.analysis.summary || "";
      }

      if (mr.recommendations) {
        advancedState.ai.moduleStates.recommendations = "completed";
        advancedState.ai.recommendationsSummary = renderRecommendationsModule(mr.recommendations);
      }
    } else {
      applyLocalAnalysisFallback(options.source || "message");
    }

    advancedState.ai.sessionState = "active";
    advancedState.ai.reviewState = advancedState.ai.missingFields.length ? "warning" : "ready";
    setDraftDirty(true);
    renderAll();
  }

  function applyDraftPatch(patch) {
    const normalized = normalizeDraftPatch(patch);
    advancedState.draft = { ...advancedState.draft, ...normalized };
    applyDraftToForm();
  }

  function applySimilarityResult(result) {
    const related = Array.isArray(result.related_ideas) ? result.related_ideas : [];
    const uniqueness = result.uniqueness != null ? String(result.uniqueness) : "—";
    const warning = result.duplicate_warning || "";

    advancedState.ai.relatedIdeas = related;
    advancedState.ai.uniquenessValue = uniqueness;
    advancedState.ai.uniquenessText =
      result.uniqueness_text ||
      tr("advanced_related_ideas", "Review AI findings, overlaps and readiness before saving.");

    advancedState.ai.similaritySummary = renderSimilarityModule({
      uniqueness: uniqueness,
      related_ideas: related,
      duplicate_warning: warning
    });

    advancedState.ai.duplicateWarning = warning || tr("status_ready", "Ready");
    advancedState.ai.moduleStates.similarity = related.length ? "completed" : "ready";
    advancedState.ai.reviewState = /strong|duplicate|blocked|совпад/i.test(warning) ? "warning" : "ready";
    advancedState.ai.reviewNote =
      result.review_note ||
      warning ||
      tr("advanced_related_ideas", "Review AI findings, overlaps and readiness before saving.");
  }

  // ============================================================
  // LOCAL FALLBACKS
  // ============================================================
  function buildStartFallback() {
    return {
      status: "ok",
      session_id: generateSessionId(),
      assistant: {
        message: tr(
          "advanced_intro_text",
          "Fill the draft or send a message so AI can begin structuring the idea."
        )
      }
    };
  }

  function buildLocalSimilarityFallback() {
    const title = advancedState.draft.title || tr("common_idea", "Idea");
    const text = [
      advancedState.draft.short_description,
      advancedState.draft.full_description,
      advancedState.draft.keywords
    ].join(" ");

    const lengthScore = Math.min(100, Math.max(30, Math.round(text.length / 15)));
    const uniqueness = Math.max(12, 100 - Math.round(lengthScore * 0.42));

    const related = [];
    if (advancedState.draft.category || advancedState.draft.keywords) {
      related.push({
        title: `${title} / ${tr("advanced_related_ideas", "Related Ideas")}`,
        score: Math.min(89, Math.max(21, 100 - uniqueness))
      });
    }

    const duplicateWarning =
      uniqueness < 45
        ? tr("advanced_duplicate_warning", "Possible strong overlap detected.")
        : tr("status_ready", "Ready");

    return {
      uniqueness: `${uniqueness}%`,
      uniqueness_text:
        uniqueness < 45
          ? tr("advanced_duplicate_warning", "Possible strong overlap detected.")
          : tr("advanced_related_ideas", "Review AI findings, overlaps and readiness before saving."),
      related_ideas: related,
      duplicate_warning: duplicateWarning,
      review_note:
        uniqueness < 45
          ? tr("advanced_review_blocked_duplicate", "Saving can be paused if a strong overlap is detected.")
          : tr("status_ready", "Ready")
    };
  }

  function applyLocalAnalysisFallback(source) {
    const d = advancedState.draft;
    const missing = computeMissingFields(d);
    const keywords = splitKeywords(d.keywords);

    const summaryLines = [];
    if (d.title) summaryLines.push(`<div><strong>${escapeHtml(d.title)}</strong></div>`);
    if (d.short_description) summaryLines.push(`<div>${escapeHtml(d.short_description)}</div>`);
    if (keywords.length) {
      summaryLines.push(
        `<div class="advanced-tag-list">${keywords.map((k) => `<span class="advanced-tag">${escapeHtml(k)}</span>`).join("")}</div>`
      );
    }

    advancedState.ai.structureSummary =
      summaryLines.join("") ||
      tr("advanced_draft_empty", "No structured draft yet.");

    advancedState.ai.analysisSummary = `
      <div><strong>${tr("module_analysis_title", "Analysis Module")}</strong></div>
      <div>${escapeHtml(buildPlainAnalysisText())}</div>
    `;

    advancedState.ai.recommendationsSummary = `
      <ul class="advanced-list">
        ${buildNextSteps().map((step) => `<li>${escapeHtml(step)}</li>`).join("")}
      </ul>
    `;

    advancedState.ai.notesAI = buildPlainAnalysisText();
    advancedState.ai.riskValue = inferRiskValue(d);
    advancedState.ai.riskText = buildRiskText(d, missing);
    advancedState.ai.missingFields = missing;
    advancedState.ai.reviewNote =
      missing.length
        ? tr("advanced_question_missing_fields", "The assistant asks only the questions needed to complete the draft.")
        : tr("status_ready", "Ready");

    advancedState.ai.moduleStates.structuring = "completed";
    advancedState.ai.moduleStates.analysis = "completed";
    advancedState.ai.moduleStates.recommendations = "completed";
    advancedState.ai.sessionState = source === "message" ? "active" : "completed";
    advancedState.ai.reviewState = missing.length ? "warning" : "ready";
  }

  function updateMissingFieldsLocal() {
    advancedState.ai.missingFields = computeMissingFields(advancedState.draft);
    advancedState.ai.reviewState = advancedState.ai.missingFields.length ? "warning" : "ready";
  }

  function computeMissingFields(draft) {
    const missing = [];

    if (!draft.title) missing.push("title");
    if (!draft.short_description) missing.push("short_description");
    if (!draft.full_description) missing.push("full_description");
    if (!draft.keywords) missing.push("keywords");
    if (!draft.category) missing.push("category");

    return missing;
  }

  function buildPlainAnalysisText() {
    const d = advancedState.draft;
    const parts = [];

    if (d.title) {
      parts.push(`${tr("field_title", "Title")}: ${d.title}.`);
    }
    if (d.category) {
      parts.push(`${tr("field_category", "Category")}: ${d.category}.`);
    }
    if (d.readiness_level) {
      parts.push(`${tr("field_readiness_level", "Readiness")}: ${d.readiness_level}.`);
    }

    const keywords = splitKeywords(d.keywords);
    if (keywords.length) {
      parts.push(`${tr("field_keywords", "Keywords")}: ${keywords.join(", ")}.`);
    }

    if (!parts.length && d.full_description) {
      parts.push(d.full_description.slice(0, 320));
    }

    return parts.join(" ");
  }

  function buildRiskText(draft, missing) {
    if (missing.length >= 4) {
      return tr("advanced_missing_fields", "Several important fields are still missing.");
    }
    if (!draft.readiness_level || !draft.patentability) {
      return tr("advanced_next_steps", "More detail is needed for a stronger evaluation.");
    }
    return tr("status_ready", "Ready");
  }

  function inferRiskValue(draft) {
    let score = 0;
    if (!draft.title) score += 1;
    if (!draft.short_description) score += 1;
    if (!draft.full_description) score += 2;
    if (!draft.keywords) score += 1;
    if (!draft.category) score += 1;
    if (!draft.readiness_level) score += 1;
    if (!draft.patentability) score += 1;

    if (score >= 5) return tr("status_warning", "Warning");
    if (score >= 3) return tr("status_review", "Review");
    return tr("status_ready", "Ready");
  }

  function buildNextSteps() {
    const d = advancedState.draft;
    const steps = [];

    if (!d.title) steps.push(tr("field_title", "Title"));
    if (!d.short_description) steps.push(tr("field_short_description", "Short Description"));
    if (!d.keywords) steps.push(tr("field_keywords", "Keywords"));
    if (!d.category) steps.push(tr("field_category", "Category"));
    if (!d.readiness_level) steps.push(tr("field_readiness_level", "Readiness"));
    if (!d.patentability) steps.push(tr("field_patentability", "Patentability"));

    if (!steps.length) {
      return [
        tr("action_check_similarity", "Check Similarity"),
        tr("action_send_to_review", "Send to Review"),
        tr("action_save_idea", "Save Idea")
      ];
    }

    return steps.map((s) => `${tr("common_fill_field", "Complete field")}: ${s}`);
  }

  function buildDraftSummaryMessage() {
    const d = advancedState.draft;
    const parts = [];

    if (d.title) parts.push(`${tr("field_title", "Title")}: ${d.title}`);
    if (d.short_description) parts.push(`${tr("field_short_description", "Short Description")}: ${d.short_description}`);
    if (d.full_description) parts.push(`${tr("field_full_description", "Full Description")}: ${d.full_description}`);
    if (d.keywords) parts.push(`${tr("field_keywords", "Keywords")}: ${d.keywords}`);
    if (d.category) parts.push(`${tr("field_category", "Category")}: ${d.category}`);
    if (d.region) parts.push(`${tr("field_region", "Region")}: ${d.region}`);
    if (d.language_original) parts.push(`${tr("field_language", "Language")}: ${d.language_original}`);
    if (d.readiness_level) parts.push(`${tr("field_readiness_level", "Readiness")}: ${d.readiness_level}`);
    if (d.patentability) parts.push(`${tr("field_patentability", "Patentability")}: ${d.patentability}`);
    if (d.confidentiality_level) parts.push(`${tr("field_confidentiality_level", "Confidentiality")}: ${d.confidentiality_level}`);
    if (d.external_links) parts.push(`${tr("field_external_links", "External Links")}: ${d.external_links}`);
    if (d.notes) parts.push(`${tr("field_notes", "Notes")}: ${d.notes}`);

    return parts.join("\n");
  }

  // ============================================================
  // RESPONSE RENDERERS
  // ============================================================
  function renderStructuringModule(data) {
    const items = [];

    if (data.summary) {
      items.push(`<div>${escapeHtml(data.summary)}</div>`);
    }

    if (data.title) {
      items.push(`<div><strong>${tr("field_title", "Title")}:</strong> ${escapeHtml(data.title)}</div>`);
    }

    if (Array.isArray(data.keywords) && data.keywords.length) {
      items.push(
        `<div class="advanced-tag-list">${data.keywords
          .map((k) => `<span class="advanced-tag">${escapeHtml(k)}</span>`)
          .join("")}</div>`
      );
    }

    return items.join("") || tr("advanced_draft_empty", "No structured draft yet.");
  }

  function renderAnalysisModule(data) {
    const items = [];

    if (data.summary) {
      items.push(`<div>${escapeHtml(data.summary)}</div>`);
    }

    if (data.risk_text) {
      items.push(`<div><strong>${tr("result_risk_title", "Risk")}:</strong> ${escapeHtml(data.risk_text)}</div>`);
    }

    if (Array.isArray(data.strengths) && data.strengths.length) {
      items.push(
        `<ul class="advanced-list">${data.strengths
          .map((s) => `<li>${escapeHtml(s)}</li>`)
          .join("")}</ul>`
      );
    }

    return items.join("") || tr("advanced_ai_waiting", "Waiting for analysis.");
  }

  function renderSimilarityModule(data) {
    const parts = [];

    if (data.uniqueness) {
      parts.push(`<div><strong>${tr("result_uniqueness_title", "Uniqueness")}:</strong> ${escapeHtml(String(data.uniqueness))}</div>`);
    }

    if (Array.isArray(data.related_ideas) && data.related_ideas.length) {
      parts.push(
        `<ul class="advanced-list">${data.related_ideas
          .map((item) => `<li>${escapeHtml(item.title || item.idea_title || tr("common_idea", "Idea"))}</li>`)
          .join("")}</ul>`
      );
    }

    if (data.duplicate_warning) {
      parts.push(`<div><strong>${escapeHtml(data.duplicate_warning)}</strong></div>`);
    }

    return parts.join("") || tr("advanced_similarity_empty", "Similarity results will appear here.");
  }

  function renderRecommendationsModule(data) {
    const items = [];

    if (data.summary) {
      items.push(`<div>${escapeHtml(data.summary)}</div>`);
    }

    if (Array.isArray(data.next_steps) && data.next_steps.length) {
      items.push(
        `<ul class="advanced-list">${data.next_steps
          .map((step) => `<li>${escapeHtml(step)}</li>`)
          .join("")}</ul>`
      );
    }

    return items.join("") || tr("advanced_next_steps", "Next steps will appear here.");
  }

  // ============================================================
  // NETWORK
  // ============================================================
  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload || {})
    });

    const text = await response.text();
    let data = {};

    try {
      data = text ? JSON.parse(text) : {};
    } catch (_) {
      data = { raw: text };
    }

    if (!response.ok) {
      const message =
        data.message ||
        data.error ||
        `HTTP ${response.status}`;
      throw new Error(message);
    }

    return data;
  }

  // ============================================================
  // CHAT HELPERS
  // ============================================================
  function pushMessage(role, content) {
    if (!content) return;
    advancedState.ai.assistantMessages.push({
      role,
      content,
      ts: Date.now()
    });
  }

  // ============================================================
  // UTILS
  // ============================================================
  function normalizeDraftPatch(patch) {
    return {
      title: patch.title || patch.idea_title || "",
      short_description: patch.short_description || patch.short || "",
      full_description: patch.full_description || patch.full || patch.description || "",
      keywords: Array.isArray(patch.keywords) ? patch.keywords.join(", ") : (patch.keywords || ""),
      category: patch.category || "",
      region: patch.region || "",
      language_original: patch.language_original || patch.language || "",
      readiness_level: patch.readiness_level || patch.readiness || "",
      patentability: patch.patentability || "",
      confidentiality_level: patch.confidentiality_level || patch.confidentiality || "",
      external_links: Array.isArray(patch.external_links) ? patch.external_links.join(", ") : (patch.external_links || ""),
      notes: patch.notes || ""
    };
  }

  function splitKeywords(value) {
    return String(value || "")
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean);
  }

  function prettifyFieldName(field) {
    const map = {
      title: tr("field_title", "Title"),
      short_description: tr("field_short_description", "Short Description"),
      full_description: tr("field_full_description", "Full Description"),
      keywords: tr("field_keywords", "Keywords"),
      category: tr("field_category", "Category"),
      region: tr("field_region", "Region"),
      language_original: tr("field_language", "Language"),
      readiness_level: tr("field_readiness_level", "Readiness"),
      patentability: tr("field_patentability", "Patentability"),
      confidentiality_level: tr("field_confidentiality_level", "Confidentiality"),
      external_links: tr("field_external_links", "External Links"),
      notes: tr("field_notes", "Notes")
    };
    return map[field] || field;
  }

  function notify(message) {
    if (!message) return;
    try {
      if (typeof window.showToast === "function") {
        window.showToast(message);
        return;
      }
    } catch (_) {}
  }

  function generateSessionId() {
    return "adv-" + Math.random().toString(36).slice(2) + "-" + Date.now().toString(36);
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatText(value) {
    const safe = escapeHtml(value || "");
    return safe.replace(/\n/g, "<br>");
  }
})();