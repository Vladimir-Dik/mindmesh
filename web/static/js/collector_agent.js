/*
Project: MindMesh
File: collector_agent.js
Version: v0.8
Date: 2026-06-22
Name: AI Collector Agent Logic (логика ИИ-агента сборщика)
*/

(function () {

  const API_RUN = "/api/collector/run";
  const API_SAVE_DRAFT = "/api/collector/save-draft";
  const API_SAVE_READY = "/api/collector/save-ready";
  const API_CHECK_DUPLICATES = "/api/collector/check-duplicates";
  const API_AUTH_ME = "/api/auth/me";
  const API_HEARTBEAT = "/api/heartbeat";

  const $ = (id) => document.getElementById(id);

  const state = {
    lastResult: null,
    lastSourceUrl: "",
    lastInstructions: "",
    sessionId: makeSessionId(),

    heartbeatOk: true,
    heartbeatTimer: null,

    duplicateChecked: false,
    duplicateFound: false,
    duplicateData: null,
    duplicateDecision: null
  };

  function makeSessionId() {
    return "MM-COL-" +
      new Date()
        .toISOString()
        .replace(/[-:.TZ]/g, "")
        .slice(0, 14);
  }

  function tr(key, fallback) {
    if (window.i18n && typeof window.i18n.t === "function") {
      return window.i18n.t(key) || fallback;
    }

    if (typeof window.t === "function") {
      return window.t(key) || fallback;
    }

    return fallback;
  }

  function log(message) {
    const box = $("collectorLog");

    if (!box) {
      return;
    }

    const time = new Date().toLocaleTimeString();

    box.textContent += `\n[${time}] ${message}`;
    box.scrollTop = box.scrollHeight;
  }

  function clearLog() {
    const box = $("collectorLog");

    if (!box) {
      return;
    }

    box.textContent = "[collector] started...";
  }

  function resetDuplicateState() {
    state.duplicateChecked = false;
    state.duplicateFound = false;
    state.duplicateData = null;
    state.duplicateDecision = null;

    const decisionBlock = $("collectorDuplicateDecisionBlock");
    const decisionStatus = $("collectorDuplicateDecisionStatus");

    if (decisionBlock) {
      decisionBlock.style.display = "none";
    }

    if (decisionStatus) {
      decisionStatus.textContent = tr(
        "collector_decision_required",
        "Select what to do with the found match."
      );
    }

    const resultBox = $("collectorDuplicateResult");
    const saveBtn = $("collectorSaveReadyBtn");
    const statusBox = $("collectorSaveStatus");
    const duplicateStatus = $("collectorDuplicateStatus");

    if (resultBox) {
      resultBox.textContent = tr(
        "collector_no_duplicate_check",
        "Duplicate analysis not started."
      );
    }

    if (saveBtn) {
      saveBtn.disabled = true;
    }

    if (statusBox) {
      statusBox.textContent = tr(
        "collector_duplicate_not_checked",
        "Duplicate check was not performed. Saving to catalog is unavailable."
      );
    }

    if (duplicateStatus) {
      duplicateStatus.textContent = tr(
        "collector_duplicate_not_checked",
        "Duplicate check was not performed. Saving to catalog is unavailable."
      );
    }
  }

  function enableSaveReady() {
    const saveBtn = $("collectorSaveReadyBtn");
    const statusBox = $("collectorSaveStatus");
    const duplicateStatus = $("collectorDuplicateStatus");

    if (saveBtn) {
      saveBtn.disabled = false;
    }

    if (statusBox) {
      statusBox.textContent = tr(
        "collector_duplicate_checked",
        "Duplicate analysis completed."
      );
    }

    if (duplicateStatus) {
      duplicateStatus.textContent = tr(
        "collector_duplicate_checked",
        "Duplicate analysis completed."
      );
    }
  }

  function showDuplicateDecisionBlock() {
    const decisionBlock = $("collectorDuplicateDecisionBlock");

    if (decisionBlock) {
      decisionBlock.style.display = "block";
    }
  }

  function getSourceData() {
    const file = $("collectorSourceFile")?.files?.[0] || null;

    return {
      file: file,
      source_url: $("collectorSourceUrl")?.value.trim() || "",
      source_type: $("collectorSourceType")?.value || "website",
      instructions: $("collectorInstructions")?.value.trim() || ""
    };
  }

  function buildRunFormData() {
    const data = getSourceData();
    const form = new FormData();

    form.append("agent_session_id", state.sessionId);
    form.append("source_url", data.source_url);
    form.append("source_type", data.source_type);
    form.append("instructions", data.instructions);
    form.append("mode", "collector_agent");
    form.append("mode_version", "Collector Agent v0.8");

    if (data.file) {
      form.append("source_file", data.file);
    }

    return { form, data };
  }

  function fillFields(result) {
    if (!result) {
      return;
    }

    const idea = result.idea || result;

    $("fieldTitle").value = idea.title || "";
    $("fieldCategory").value = idea.category || "";
    $("fieldLanguage").value = idea.language || "";
    $("fieldRegion").value = idea.region || "";

    $("fieldKeywords").value = Array.isArray(idea.keywords)
      ? idea.keywords.join(", ")
      : (idea.keywords || "");

    $("fieldAITags").value = Array.isArray(idea.ai_tags)
      ? idea.ai_tags.join(", ")
      : (idea.ai_tags || "");

    $("fieldShortDescription").value =
      idea.short_description ||
      idea.short ||
      "";

    $("fieldFullDescription").value =
      idea.full_description ||
      idea.full ||
      "";

    $("fieldExistingAnalogues").value =
      idea.existing_analogues || "";

    $("fieldNotesAI").value =
      idea.notes_ai ||
      idea.ai_comment ||
      "";

    $("fieldPatentability").value =
      idea.patentability || "unknown";

    $("fieldSource").value =
      idea.source ||
      state.lastSourceUrl ||
      "";

    $("fieldAIReviewStatus").value =
      idea.ai_review_status || "draft";
  }

  function collectIdeaFields() {
    return {
      title: $("fieldTitle")?.value.trim() || "",
      category: $("fieldCategory")?.value.trim() || "",
      language: $("fieldLanguage")?.value.trim() || "",
      region: $("fieldRegion")?.value.trim() || "",
      keywords: $("fieldKeywords")?.value.trim() || "",
      ai_tags: $("fieldAITags")?.value.trim() || "",
      short_description: $("fieldShortDescription")?.value.trim() || "",
      full_description: $("fieldFullDescription")?.value.trim() || "",
      existing_analogues: $("fieldExistingAnalogues")?.value.trim() || "",
      notes_ai: $("fieldNotesAI")?.value.trim() || "",
      patentability: $("fieldPatentability")?.value.trim() || "",
      source: $("fieldSource")?.value.trim() || "",
      ai_review_status: $("fieldAIReviewStatus")?.value.trim() || "draft",
      discovered_by_ai: true,
      intake_mode: "collector_agent",
      agent_session_id: state.sessionId,
      collector_version: "Collector Agent v0.8"
    };
  }

  async function runAgent(isRetry = false) {
    resetDuplicateState();
    

  const auth = await checkAuthBeforeSave();

  if (!auth) {
    return;
  }
    

    const { form, data } = buildRunFormData();

    if (!data.source_url && !data.file) {
      log(
        tr(
          "collector_error_no_source",
          "Source URL or file is required."
        )
      );

      return;
    }

    clearLog();
    
   log("[collector] started...");
    
   log(
     tr(
       "collector_working",
       "Working... please wait."
     )
   );
    

    state.lastSourceUrl =
      data.source_url ||
      (data.file ? data.file.name : "");

    state.lastInstructions = data.instructions;

    log(
      isRetry
        ? tr(
            "collector_log_retry",
            "Retry started with new instructions."
          )
        : tr(
            "collector_log_started",
            "Agent run started."
          )
    );

    if (data.file) {
      log(
        tr("collector_log_file_selected", "File selected:") +
        " " +
        data.file.name +
        " (" +
        data.file.type +
        ", " +
        data.file.size +
        " bytes)"
      );
    }

    log(
      tr(
        "collector_log_fetch",
        "Sending source to server..."
      )
    );

    try {
      const response = await fetch(
        API_RUN,
        {
          method: "POST",
          body: form
        }
      );

      const json = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        log(
          json.message ||
          json.error ||
          tr(
            "collector_error_server",
            "Server error."
          )
        );

        return;
      }

      state.lastResult = json;

      log(
        tr(
          "collector_log_received",
          "Result received."
        )
      );

      if (Array.isArray(json.log)) {
        json.log.forEach((item) => log(item));
      }

      fillFields(json);

      log(
        tr(
          "collector_log_ready",
          "Fields prepared for review."
        )
      );

    } catch (error) {
      log(
        tr(
          "collector_error_network",
          "Network error."
        ) +
        " " +
        error.message
      );
    }
  }

  async function checkDuplicates() {
    const idea = collectIdeaFields();

    log(
      tr(
        "collector_duplicate_check_started",
        "Checking duplicates..."
      )
    );

    try {
      const response = await fetch(
        API_CHECK_DUPLICATES,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            idea: idea
          })
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        log(
          data.message ||
          tr(
            "collector_duplicate_check_failed",
            "Duplicate check failed."
          )
        );

        return;
      }

      state.duplicateChecked = true;
      state.duplicateData = data;

      const box = $("collectorDuplicateResult");

      if (!box) {
        return;
      }

      if (!data.duplicate_found) {
        state.duplicateFound = false;
        state.duplicateDecision = null;

        box.innerHTML = `
          <div class="duplicate-ok">
            ${tr(
              "collector_duplicate_none",
              "No similar ideas found."
            )}
          </div>
        `;

        log(
          tr(
            "collector_duplicate_none",
            "No similar ideas found."
          )
        );

        enableSaveReady();

        return;
      }

      state.duplicateFound = true;
      state.duplicateDecision = null;

      showDuplicateDecisionBlock();
      
      const duplicateStatus = $("collectorDuplicateStatus");
      
      if (duplicateStatus) {
        duplicateStatus.textContent =
          tr(
            "collector_duplicate_found",
            "Possible duplicate found"
          ) +
          ": " +
          data.similarity_score +
          "%";
      }

      box.innerHTML = `
        <div class="duplicate-warning">

          <div>
            <strong>
              ${tr(
                "collector_duplicate_found",
                "Possible duplicate found"
              )}
            </strong>
          </div>

          <div>
            ${tr(
              "simple_result_similarity_label",
              "Similarity"
            )}:
            ${data.similarity_score}%
          </div>

          <hr>

          <div>
            <strong>
              ${data.idea.title || "Untitled"}
            </strong>
          </div>

          <div>
            IdeaID:
            ${data.idea.idea_id || ""}
          </div>

          <div>
            ${tr(
              "collector_status",
              "Status"
            )}:
            ${data.idea.status || ""}
          </div>

        </div>
      `;

      const saveBtn = $("collectorSaveReadyBtn");

      if (saveBtn) {
        saveBtn.disabled = true;
      }

      const statusBox = $("collectorSaveStatus");

      if (statusBox) {
        statusBox.textContent = tr(
          "collector_decision_required",
          "Select what to do with the found match."
        );
      }

      log(
        tr(
          "collector_duplicate_found",
          "Possible duplicate found"
        )
      );

    } catch (error) {
      log(
        tr(
          "collector_duplicate_check_failed",
          "Duplicate check failed."
        ) +
        " " +
        error.message
      );
    }
  }

  function setDuplicateDecision(decision) {
    state.duplicateDecision = decision;

    const decisionStatus = $("collectorDuplicateDecisionStatus");

    if (decisionStatus) {
      decisionStatus.textContent =
        tr(
          "collector_decision_selected",
          "Selected decision:"
        ) +
        " " +
        decision;
    }

    if (
      decision === "linked_duplicate" ||
      decision === "send_to_review"
    ) {
      enableSaveReady();
    }

    if (decision === "draft_without_link") {
      saveResult(API_SAVE_DRAFT, "draft");
    }
  }

  async function checkAuthBeforeSave() {
    try {
      const response = await fetch(
        API_AUTH_ME,
        {
          method: "GET",
          cache: "no-store"
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!data.is_authenticated) {
        log(
          tr(
            "collector_error_auth_required",
            "Authorization required. Please login again."
          )
        );

        window.location.href = "/login?next=/collector";

        return null;
      }

      return data;

    } catch (error) {
      log(
        tr(
          "collector_error_auth_check",
          "Authorization check failed."
        )
      );

      return null;
    }
  }

  async function heartbeat() {
    try {
      const response = await fetch(
        API_HEARTBEAT,
        {
          method: "GET",
          cache: "no-store"
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (
        !response.ok ||
        data.status === "degraded"
      ) {
        if (state.heartbeatOk) {
          log(
            tr(
              "collector_heartbeat_lost",
              "Connection degraded. Trying to reconnect..."
            )
          );
        }

        state.heartbeatOk = false;

        return;
      }

      if (
        !data.session ||
        !data.session.authenticated
      ) {

        log(
          tr(
            "collector_session_expired",
            "Session expired. Please login again before saving."
          )
        );

        state.heartbeatOk = false;

        return;
}

      if (!state.heartbeatOk) {
        log(
          tr(
            "collector_heartbeat_restored",
            "Connection restored."
          )
        );
      }

      state.heartbeatOk = true;

    } catch (error) {
      if (state.heartbeatOk) {
        log(
          tr(
            "collector_heartbeat_lost",
            "Connection degraded. Trying to reconnect..."
          )
        );
      }

      state.heartbeatOk = false;
    }
  }

  function startHeartbeat() {
    heartbeat();

    state.heartbeatTimer = setInterval(
      () => {
        heartbeat();
      },
      60000
    );
  }

  async function saveResult(endpoint, statusValue) {
    if (
      statusValue === "ready" &&
      !state.duplicateChecked
    ) {
      log(
        tr(
          "collector_save_ready_blocked",
          "Perform duplicate check first."
        )
      );

      return;
    }

    if (
      statusValue === "ready" &&
      state.duplicateFound &&
      !state.duplicateDecision
    ) {
      log(
        tr(
          "collector_decision_required",
          "Select what to do with the found match."
        )
      );

      return;
    }

    const auth = await checkAuthBeforeSave();

    if (!auth) {
      return;
    }

    const idea = collectIdeaFields();

    idea.ai_review_status = statusValue;

    log(
      statusValue === "ready"
        ? tr(
            "collector_log_save_ready",
            "Saving as ready idea..."
          )
        : tr(
            "collector_log_save_draft",
            "Saving draft..."
          )
    );

    try {
      const response = await fetch(
        endpoint,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            agent_session_id: state.sessionId,
            source_url: state.lastSourceUrl,
            instructions: state.lastInstructions,
            duplicate_data: state.duplicateData,
            duplicate_decision: state.duplicateDecision,
            idea: idea,
            raw_agent_result: state.lastResult
          })
        }
      );

      const data = await response
        .json()
        .catch(() => ({}));

      if (!response.ok) {
        if (
          response.status === 401 ||
          response.status === 403
        ) {
          log(
            tr(
              "collector_error_auth_required",
              "Authorization required. Please login again."
            )
          );

          window.location.href = "/login?next=/collector";

          return;
        }

        log(
          data.message ||
          data.error ||
          tr(
            "collector_error_save",
            "Save failed."
          )
        );

        return;
      }


       log(
        tr(
          "collector_log_saved",
          "Saved."
        ) +
        (
          data.idea_id
            ? " ID: " + data.idea_id
            : ""
        )
      );

      if (data.review_required) {

        log(
          tr(
            "collector_sent_to_review",
             "Idea sent to moderation queue."
          )
         );

        log(
          tr(
            "collector_review_reason",
            "Reason:"
          ) +
          " " +
          (data.review_reason || "")
        );

      }

      let msg =
        tr(
          "collector_log_saved",
          "Saved."
        );

      if (data.idea_id) {
        msg += "\nID: " + data.idea_id;
      }

      if (data.status_name) {
        msg +=
          "\n" +
          tr(
            "collector_status",
            "Status"
          ) +
          ": " +
          data.status_name;
      }

      if (data.review_queue) {
        msg +=
          "\n" +
          tr(
            "collector_review_queue",
            "Queue"
          ) +
          ": " +
          data.review_queue;
      }

      if (data.review_required) {

        msg +=
          "\n\n" +
          tr(
            "collector_review_required",
            "Moderator review required."
          );

      }

      if (data.duplicate_found) {

        msg +=
          "\n\n" +
          tr(
            "collector_duplicate_found",
            "Duplicate found"
          );

        if (data.duplicate_title) {
          msg += "\n" + data.duplicate_title;
        }

        if (data.similarity_score) {

          msg +=
            "\n" +
            tr(
              "simple_result_similarity_label",
              "Similarity"
            ) +
            ": " +
            data.similarity_score +
            "%";
        }
      }

      alert(msg);

    } catch (error) {
      log(
        tr(
          "collector_error_network",
          "Network error."
        ) +
        " " +
        error.message
      );
    }
  }

  function bindEvents() {
    $("collectorBackBtn")
      ?.addEventListener(
        "click",
        () => {
          if (
            document.referrer &&
            document.referrer.includes(
              window.location.origin
            )
          ) {
            window.history.back();
          } else {
            window.location.href = "/login";
          }
        }
      );

    $("collectorRunBtn")
      ?.addEventListener(
        "click",
        () => runAgent(false)
      );

    $("collectorRetryBtn")
      ?.addEventListener(
        "click",
        () => runAgent(true)
      );

    $("collectorCheckDuplicatesBtn")
      ?.addEventListener(
        "click",
        () => checkDuplicates()
      );

    $("collectorDecisionLinkedDuplicateBtn")
      ?.addEventListener(
        "click",
        () => {
          setDuplicateDecision("linked_duplicate");
        }
      );

    $("collectorDecisionDraftNoLinkBtn")
      ?.addEventListener(
        "click",
        () => {
          setDuplicateDecision("draft_without_link");
        }
      );

    $("collectorDecisionSendReviewBtn")
      ?.addEventListener(
        "click",
        () => {
          setDuplicateDecision("send_to_review");
        }
      );

    $("collectorSaveDraftBtn")
      ?.addEventListener(
        "click",
        () => {
          saveResult(
            API_SAVE_DRAFT,
            "draft"
          );
        }
      );

    $("collectorSaveReadyBtn")
      ?.addEventListener(
        "click",
        () => {
          saveResult(
            API_SAVE_READY,
            "ready"
          );
        }
      );
  }

  document.addEventListener(
    "DOMContentLoaded",
    () => {
      bindEvents();
      startHeartbeat();
      resetDuplicateState();

      log(
        "Collector Agent v0.8 ready."
      );
    }
  );

})();