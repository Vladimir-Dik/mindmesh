/*
============================================================
Project: MindMesh
File: user_management.js
Version: 1.1
Date: 10.04.2026
Purpose:
- Frontend logic for user_management.html
- Load user stats, list and card
- Edit main statuses, AccessControl, PrivacyControl
============================================================
*/

(function () {
  "use strict";

  const state = {
    users: [],
    filteredUsers: [],
    selectedUser: null,
    activeQuickFilter: "all"
  };

  function qs(id) {
    return document.getElementById(id);
  }

  function setText(id, value) {
    const el = qs(id);
    if (el) {
      el.textContent = value ?? "-";
    }
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function toArray(value) {
    if (Array.isArray(value)) return value;
    if (typeof value === "string" && value.trim()) {
      return value
        .split(",")
        .map(v => v.trim())
        .filter(Boolean);
    }
    return [];
  }

  function toBool01(value) {
    return value === true || value === 1 || value === "1" || value === "true" ? "1" : "0";
  }

  function parseControlString(str) {
    const result = {};
    if (!str || typeof str !== "string") return result;

    str.split("|").forEach(pair => {
      const [rawKey, rawValue] = pair.split(":");
      const key = (rawKey || "").trim();
      const value = (rawValue || "").trim();
      if (!key) return;
      result[key] = value;
    });

    return result;
  }

  function buildControlString(obj, orderedKeys) {
    return orderedKeys
      .map(key => `${key}:${obj[key] ?? 0}`)
      .join("|");
  }

  function formatDate(value) {
    if (!value) return "-";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleString();
  }

  function getDisplayName(user) {
    const full = [user.name, user.last_name].filter(Boolean).join(" ").trim();
    return full || user.email || user.user_id || "—";
  }

  function getAccessFlagsFromUI() {
    return {
      advanced: qs("um_access_advanced")?.checked ? "1" : "0",
      reviewer_panel: qs("um_access_reviewer_panel")?.checked ? "1" : "0",
      admin_panel: qs("um_access_admin_panel")?.checked ? "1" : "0",
      external_links: qs("um_access_external_links")?.checked ? "1" : "0",
      readonly: qs("um_access_readonly")?.checked ? "1" : "0",
      ban: qs("um_access_ban")?.checked ? "1" : "0"
    };
  }

  function getPrivacyFlagsFromUI() {
    return {
      profile: qs("um_privacy_profile")?.checked ? "1" : "0",
      email: qs("um_privacy_email")?.checked ? "1" : "0",
      contacts: qs("um_privacy_contacts")?.checked ? "1" : "0",
      location: qs("um_privacy_location")?.checked ? "1" : "0",
      bio: qs("um_privacy_bio")?.checked ? "1" : "0",
      author_visible: qs("um_privacy_author_visible")?.checked ? "1" : "0",
      search: qs("um_privacy_search")?.checked ? "1" : "0"
    };
  }

  function buildAccessControlForSelectedUser() {
    if (!state.selectedUser) return "-";

    const role = qs("um_edit_role")?.value || state.selectedUser.role || "user";
    const verified = qs("um_edit_verified")?.value || toBool01(state.selectedUser.is_verified);
    const account = qs("um_edit_account_status")?.value || state.selectedUser.account_status || "active";
    const subscription = (qs("um_edit_subscription")?.value || "").trim() || "free";

    const manualFlags = getAccessFlagsFromUI();

    return buildControlString(
      {
        role,
        verified,
        account,
        subscription,
        advanced: manualFlags.advanced,
        reviewer_panel: manualFlags.reviewer_panel,
        admin_panel: manualFlags.admin_panel,
        external_links: manualFlags.external_links,
        readonly: manualFlags.readonly,
        ban: manualFlags.ban
      },
      [
        "role",
        "verified",
        "account",
        "subscription",
        "advanced",
        "reviewer_panel",
        "admin_panel",
        "external_links",
        "readonly",
        "ban"
      ]
    );
  }

  function buildPrivacyControlForSelectedUser() {
    if (!state.selectedUser) return "-";

    const flags = getPrivacyFlagsFromUI();

    return buildControlString(
      flags,
      ["profile", "email", "contacts", "location", "bio", "author_visible", "search"]
    );
  }

  function updateControlPreviews() {
    setText("um_access_control_preview", buildAccessControlForSelectedUser());
    setText("um_privacy_control_preview", buildPrivacyControlForSelectedUser());
  }

  function normalizeUserRecord(raw) {
    const accessFlags = parseControlString(raw.access_control || "");
    const privacyFlags = parseControlString(raw.privacy_control || "");
    const subscriptionArray = Array.isArray(raw.subscription_status)
      ? raw.subscription_status
      : toArray(raw.subscription_status);

    return {
      record_id: raw.record_id || raw.id || "",
      user_id: raw.user_id || "",
      name: raw.name || "",
      last_name: raw.last_name || "",
      email: raw.email || "",
      role: raw.role || "user",
      created_at: raw.created_at || "",
      last_visit_at: raw.last_visit_at || "",
      visit_count: Number(raw.visit_count || 0),
      ideas_created_count: Number(raw.ideas_created_count || 0),
      language: raw.language || raw.preferred_language || "",
      preferred_language: raw.preferred_language || "",
      is_verified: !!raw.is_verified,
      verification_level: raw.verification_level || "",
      account_status: raw.account_status || "active",
      subscription_status: subscriptionArray,
      subscription_text: subscriptionArray.join(", "),
      reviewer_score: Number(raw.reviewer_score || 0),
      reviews_completed: Number(raw.reviews_completed || 0),
      reviews_approved: Number(raw.reviews_approved || 0),
      reviews_rejected: Number(raw.reviews_rejected || 0),
      profile_edit_count: Number(raw.profile_edit_count || 0),
      unanswered_feedback: Number(raw.unanswered_feedback || 0),
      access_control: raw.access_control || "",
      privacy_control: raw.privacy_control || "",
      access_flags: accessFlags,
      privacy_flags: privacyFlags,
      user_log: Array.isArray(raw.user_log) ? raw.user_log : []
    };
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    let data = {};
    try {
      data = await response.json();
    } catch (e) {
      data = {};
    }

    if (!response.ok) {
      throw new Error(data.error || data.message || `HTTP ${response.status}`);
    }

    return data;
  }

  function matchesQuickFilter(user, filterName) {
    const role = (user.role || "").toLowerCase();
    const accountStatus = (user.account_status || "").toLowerCase();
    const subscriptionText = (user.subscription_text || "").toLowerCase();

    switch (filterName) {
      case "authorized":
        return !!user.last_visit_at || user.visit_count > 0;
      case "verified":
        return !!user.is_verified;
      case "admin":
        return ["admin", "topadmin", "superadmin"].includes(role);
      case "moderator":
        return role === "moderator";
      case "reviewer":
        return role === "reviewer";
      case "vip":
        return subscriptionText.includes("vip") || subscriptionText.includes("friend");
      case "banned":
        return accountStatus === "banned" || user.access_flags?.ban === "1";
      case "unanswered":
        return user.unanswered_feedback > 0;
      case "all":
      default:
        return true;
    }
  }

  function matchesSearchAndFilters(user) {
    const query = (qs("um_search")?.value || "").trim().toLowerCase();
    const roleFilter = (qs("um_role_filter")?.value || "").trim().toLowerCase();
    const statusFilter = (qs("um_status_filter")?.value || "").trim().toLowerCase();
    const verifiedFilter = qs("um_verified_filter")?.value || "";

    const haystack = [
      user.name,
      user.last_name,
      user.email,
      user.user_id,
      user.role,
      user.account_status
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    if (query && !haystack.includes(query)) return false;
    if (roleFilter && (user.role || "").toLowerCase() !== roleFilter) return false;
    if (statusFilter && (user.account_status || "").toLowerCase() !== statusFilter) return false;
    if (verifiedFilter !== "" && toBool01(user.is_verified) !== verifiedFilter) return false;

    return matchesQuickFilter(user, state.activeQuickFilter);
  }

  function renderStats(stats) {
    setText("um_total_users", stats.total_users ?? 0);
    setText("um_authorized_users", stats.authorized_users ?? 0);
    setText("um_verified_users", stats.verified_users ?? 0);
    setText("um_admin_users", stats.admin_users ?? 0);
    setText("um_moderator_users", stats.moderator_users ?? 0);
    setText("um_reviewer_users", stats.reviewer_users ?? 0);
    setText("um_banned_users", stats.banned_users ?? 0);
    setText("um_unanswered_users", stats.unanswered_users ?? 0);
  }

  function getRoleBadges(user) {
    const badges = [];

    badges.push(`<span class="badge" style="margin-right:6px;">${escapeHtml(user.role || "user")}</span>`);

    if (user.is_verified) {
      badges.push(`<span class="badge" style="margin-right:6px;">verified</span>`);
    }

    if ((user.account_status || "").toLowerCase() === "banned" || user.access_flags?.ban === "1") {
      badges.push(`<span class="badge" style="margin-right:6px;">banned</span>`);
    }

    if (user.unanswered_feedback > 0) {
      badges.push(`<span class="badge" style="margin-right:6px;">feedback</span>`);
    }

    return badges.join("");
  }

function renderUsersList() {
  const listEl = qs("um_users_list");
  if (!listEl) return;

  setText("um_list_count", state.filteredUsers.length);

  if (!state.filteredUsers.length) {
    listEl.innerHTML = `<div class="log-item">Нет пользователей</div>`;
    return;
  }

  listEl.innerHTML = state.filteredUsers.map(user => {

    const name = getDisplayName(user) || "—";
    const email = user.email || "—";
    const role = user.role || "user";
    const status = user.account_status || "—";
    const userId = user.user_id || "—";

    return `
      <div 
        class="log-item um-user-row"
        data-record-id="${escapeHtml(user.record_id)}"
        style="cursor:pointer; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"
      >
        ${escapeHtml(name)} | ${escapeHtml(email)} | ${escapeHtml(role)} | ${escapeHtml(status)} | ${escapeHtml(userId)}
      </div>
    `;
  }).join("");

  // Клик → переход в user_card
  listEl.querySelectorAll(".um-user-row").forEach(row => {
    row.addEventListener("click", () => {
      const recordId = row.getAttribute("data-record-id");
      if (!recordId) return;

      window.location.href = `/user_card?record_id=${encodeURIComponent(recordId)}`;
    });
  });
}

  function renderUserLog(items) {
    const el = qs("um_user_log");
    if (!el) return;

    if (!items || !items.length) {
      el.innerHTML = `<div class="log-item">Нет данных</div>`;
      return;
    }

    el.innerHTML = items.map(item => `
      <div class="log-item">
        <div style="font-weight:700;">${escapeHtml(item.title || item.type || "event")}</div>
        <div style="opacity:0.75; margin-top:4px;">${escapeHtml(item.text || item.notes || "")}</div>
        <div style="opacity:0.65; margin-top:6px;">${escapeHtml(formatDate(item.timestamp || item.created_at))}</div>
      </div>
    `).join("");
  }

  function renderSelectedUser() {
    const user = state.selectedUser;
    if (!user) return;

    setText("um_card_name", getDisplayName(user));
    setText("um_card_email", user.email || "—");

    setText("um_card_userid", user.user_id || "—");
    setText("um_card_role", user.role || "—");
    setText("um_card_created", formatDate(user.created_at));
    setText("um_card_last_visit", formatDate(user.last_visit_at));
    setText("um_card_visit_count", user.visit_count ?? 0);
    setText("um_card_ideas_count", user.ideas_created_count ?? 0);
    setText("um_card_verified", user.is_verified ? "Yes" : "No");
    setText("um_card_account_status", user.account_status || "—");
    setText("um_card_subscription", user.subscription_text || "—");
    setText("um_card_language", user.language || "—");

    setText("um_card_reviews_completed", user.reviews_completed ?? 0);
    setText("um_card_reviews_approved", user.reviews_approved ?? 0);
    setText("um_card_reviews_rejected", user.reviews_rejected ?? 0);
    setText("um_card_reviewer_score", user.reviewer_score ?? 0);
    setText("um_card_profile_edits", user.profile_edit_count ?? 0);
    setText("um_card_unanswered_feedback", user.unanswered_feedback ?? 0);

    if (qs("um_edit_role")) qs("um_edit_role").value = user.role || "user";
    if (qs("um_edit_account_status")) qs("um_edit_account_status").value = user.account_status || "active";
    if (qs("um_edit_verified")) qs("um_edit_verified").value = user.is_verified ? "1" : "0";
    if (qs("um_edit_verification_level")) qs("um_edit_verification_level").value = user.verification_level || "";
    if (qs("um_edit_subscription")) qs("um_edit_subscription").value = user.subscription_text || "";

    const access = user.access_flags || {};
    if (qs("um_access_advanced")) qs("um_access_advanced").checked = access.advanced === "1";
    if (qs("um_access_reviewer_panel")) qs("um_access_reviewer_panel").checked = access.reviewer_panel === "1";
    if (qs("um_access_admin_panel")) qs("um_access_admin_panel").checked = access.admin_panel === "1";
    if (qs("um_access_external_links")) qs("um_access_external_links").checked = access.external_links === "1";
    if (qs("um_access_readonly")) qs("um_access_readonly").checked = access.readonly === "1";
    if (qs("um_access_ban")) qs("um_access_ban").checked = access.ban === "1";

    const privacy = user.privacy_flags || {};
    if (qs("um_privacy_profile")) qs("um_privacy_profile").checked = privacy.profile === "1";
    if (qs("um_privacy_email")) qs("um_privacy_email").checked = privacy.email === "1";
    if (qs("um_privacy_contacts")) qs("um_privacy_contacts").checked = privacy.contacts === "1";
    if (qs("um_privacy_location")) qs("um_privacy_location").checked = privacy.location === "1";
    if (qs("um_privacy_bio")) qs("um_privacy_bio").checked = privacy.bio === "1";
    if (qs("um_privacy_author_visible")) qs("um_privacy_author_visible").checked = privacy.author_visible === "1";
    if (qs("um_privacy_search")) qs("um_privacy_search").checked = privacy.search === "1";

    renderUserLog(user.user_log || []);
    updateControlPreviews();
  }

  function applyFilters() {
    state.filteredUsers = state.users.filter(matchesSearchAndFilters);
    renderUsersList();
  }

  async function loadUserManagementData() {
    const data = await fetchJson("/api/user-management/overview");
    const users = Array.isArray(data.users) ? data.users.map(normalizeUserRecord) : [];
    const stats = data.stats || {};

    state.users = users;
    state.filteredUsers = users;

    renderStats(stats);

    if (!state.selectedUser && users.length) {
      state.selectedUser = users[0];
    } else if (state.selectedUser) {
      const found = users.find(u => u.record_id === state.selectedUser.record_id);
      state.selectedUser = found || users[0] || null;
    }

    applyFilters();

    if (state.selectedUser) {
      renderSelectedUser();
    }
  }

  async function saveMainStatuses() {
    if (!state.selectedUser) {
      alert("Сначала выберите пользователя.");
      return;
    }

    const payload = {
      record_id: state.selectedUser.record_id,
      role: qs("um_edit_role")?.value || "user",
      account_status: qs("um_edit_account_status")?.value || "active",
      is_verified: (qs("um_edit_verified")?.value || "0") === "1",
      verification_level: qs("um_edit_verification_level")?.value || "",
      subscription_status: toArray(qs("um_edit_subscription")?.value || "")
    };

    await fetchJson("/api/user-management/update-main", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    await loadUserManagementData();
    alert("Основные статусы сохранены.");
  }

  async function saveAccessControl() {
    if (!state.selectedUser) {
      alert("Сначала выберите пользователя.");
      return;
    }

    const payload = {
      record_id: state.selectedUser.record_id,
      access_control: buildAccessControlForSelectedUser()
    };

    await fetchJson("/api/user-management/update-access", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    await loadUserManagementData();
    alert("Права доступа сохранены.");
  }

  async function savePrivacyControl() {
    if (!state.selectedUser) {
      alert("Сначала выберите пользователя.");
      return;
    }

    const payload = {
      record_id: state.selectedUser.record_id,
      privacy_control: buildPrivacyControlForSelectedUser()
    };

    await fetchJson("/api/user-management/update-privacy", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    await loadUserManagementData();
    alert("Приватность сохранена.");
  }

  function bindQuickFilters() {
    document.querySelectorAll(".user-filter-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".user-filter-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.activeQuickFilter = btn.getAttribute("data-filter") || "all";
        applyFilters();
      });
    });
  }

  function bindFieldWatchers() {
    [
      "um_search",
      "um_role_filter",
      "um_status_filter",
      "um_verified_filter"
    ].forEach(id => {
      qs(id)?.addEventListener("input", applyFilters);
      qs(id)?.addEventListener("change", applyFilters);
    });

    [
      "um_edit_role",
      "um_edit_account_status",
      "um_edit_verified",
      "um_edit_verification_level",
      "um_edit_subscription",
      "um_access_advanced",
      "um_access_reviewer_panel",
      "um_access_admin_panel",
      "um_access_external_links",
      "um_access_readonly",
      "um_access_ban",
      "um_privacy_profile",
      "um_privacy_email",
      "um_privacy_contacts",
      "um_privacy_location",
      "um_privacy_bio",
      "um_privacy_author_visible",
      "um_privacy_search"
    ].forEach(id => {
      qs(id)?.addEventListener("input", updateControlPreviews);
      qs(id)?.addEventListener("change", updateControlPreviews);
    });
  }

  function bindButtons() {
    qs("user_mgmt_refresh_btn")?.addEventListener("click", async () => {
      try {
        await loadUserManagementData();
      } catch (err) {
        alert(err.message || "Ошибка обновления.");
      }
    });

    qs("um_save_main_btn")?.addEventListener("click", async () => {
      try {
        await saveMainStatuses();
      } catch (err) {
        alert(err.message || "Ошибка сохранения основных статусов.");
      }
    });

    qs("um_save_access_btn")?.addEventListener("click", async () => {
      try {
        await saveAccessControl();
      } catch (err) {
        alert(err.message || "Ошибка сохранения доступа.");
      }
    });

    qs("um_save_privacy_btn")?.addEventListener("click", async () => {
      try {
        await savePrivacyControl();
      } catch (err) {
        alert(err.message || "Ошибка сохранения приватности.");
      }
    });

    qs("um_reset_password_btn")?.addEventListener("click", () => {
      alert("Кнопка подготовлена. Backend для сброса пароля подключим отдельно.");
    });

    qs("um_assign_admin_btn")?.addEventListener("click", () => {
      alert("Кнопка подготовлена. Логику перенаправления подключим отдельно.");
    });

    qs("um_toggle_ban_btn")?.addEventListener("click", () => {
      const banEl = qs("um_access_ban");
      if (banEl) {
        banEl.checked = !banEl.checked;
        updateControlPreviews();
      }
    });

    qs("um_toggle_privilege_btn")?.addEventListener("click", () => {
      alert("Кнопка подготовлена. Логику привилегий подключим отдельно.");
    });

    qs("um_delete_user_btn")?.addEventListener("click", () => {
      alert("Кнопка подготовлена. Удаление подключим отдельно после backend-проверок.");
    });

    qs("um_open_messages_btn")?.addEventListener("click", () => {
      alert("Переход к сообщениям пользователя подключим отдельно.");
    });

    qs("um_open_ideas_btn")?.addEventListener("click", () => {
      alert("Переход к идеям пользователя подключим отдельно.");
    });
  }

  async function init() {
    bindQuickFilters();
    bindFieldWatchers();
    bindButtons();

    try {
      await loadUserManagementData();
    } catch (err) {
      const listEl = qs("um_users_list");
      if (listEl) {
        listEl.innerHTML = `<div class="log-item">Ошибка загрузки: ${escapeHtml(err.message || "unknown error")}</div>`;
      }
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();