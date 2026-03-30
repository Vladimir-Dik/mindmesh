/*
============================================================
Project: MindMesh
File: system_workdesk.js
Version: 1.2
Date: 2026-03-12
Purpose:
SuperAdmin / System Workdesk control script.

Functions:
- Load users list
- Load system log
- Load system status
- Show colored system indicators
- Toggle system modes
- Apply system configuration
- Display users statistics
============================================================
*/

async function loadUsers() {
  const container = document.getElementById("users");
  if (!container) return;

  const res = await fetch("/api/admin/users");
  const data = await res.json();

  if (!data.users) return;

  let html = "<ul>";

  data.users.forEach((u) => {
    html += `<li>${u.email} (${u.role})</li>`;
  });

  html += "</ul>";
  container.innerHTML = html;
}

async function loadLog() {

  const container = document.getElementById("log-preview");
  if (!container) return;

  const res = await fetch("/api/system/log");
  const data = await res.json();

  if (!data.log) return;

  let html = "";

  data.log.slice(-3).reverse().forEach(entry => {
    html += `<div>▶ ${entry}</div>`;
  });

  container.innerHTML = html;
}


async function toggleTest() {
  await fetch("/api/system/toggle-test", {
    method: "POST"
  });
  location.reload();
}

async function setSoft() {
  await fetch("/api/system/maintenance/soft", {
    method: "POST"
  });
  location.reload();
}

async function setFull() {
  await fetch("/api/system/maintenance/full", {
    method: "POST"
  });
  location.reload();
}

async function disableMaint() {
  await fetch("/api/system/maintenance/disable", {
    method: "POST"
  });
  location.reload();
}

async function loadSystemStatus() {
  const res = await fetch("/api/system/state");
  const data = await res.json();

  const test = document.getElementById("testModeStatus");
  const maint = document.getElementById("maintenanceStatus");
  const db = document.getElementById("databaseStatus");

  if (!data) return;

  if (test) {
    if (data.test_mode) {
      test.textContent = "ON";
      test.className = "status-warn";
    } else {
      test.textContent = "OFF";
      test.className = "status-ok";
    }
  }

  if (maint) {
    if (data.maintenance === "none") {
      maint.textContent = "none";
      maint.className = "status-ok";
    } else if (data.maintenance === "soft") {
      maint.textContent = "soft";
      maint.className = "status-warn";
    } else {
      maint.textContent = "full";
      maint.className = "status-error";
    }
  }

  // Пока отдельного API статуса базы нет:
  // если системное состояние загрузилось, показываем OK
  if (db) {
    db.textContent = "OK";
    db.className = "status-ok";
  }
}

async function loadUsersCount() {
  try {
    const r = await fetch("/api/admin/users_count");
    const data = await r.json();

    const el = document.getElementById("total_users");
    if (!el) return;

    if (typeof data.total_users !== "number") {
      el.innerText = "0";
      return;
    }

    el.innerText = formatNumber(data.total_users);

  } catch (e) {
    console.error("Users count error:", e);

    const el = document.getElementById("total_users");
    if (el) {
      el.innerText = "ERR";
    }
  }
}

function formatNumber(num) {
  if (num >= 1000000000) return (num / 1000000000).toFixed(1) + "G";
  if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
  if (num >= 1000) return (num / 1000).toFixed(1) + "K";
  return String(num);
}

function openUsersPanel() {
  window.location.href = "/searchwave/users";
}

function scrollToLog() {
  const log = document.getElementById("system-log");
  if (!log) return;
  log.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadCurrentUser(){

  try{

    const r = await fetch("/api/auth/me");

    if(!r.ok){
      console.error("auth/me failed:", r.status);
      return;
    }

    const data = await r.json();

    const name = document.getElementById("currentUserName");
    const email = document.getElementById("currentUserEmail");
    const role = document.getElementById("currentUserRole");
    const auth = document.getElementById("currentUserAuth");
    const access = document.getElementById("currentUserAccess");

    if(name) name.innerText = data.name || "Guest";
    if(email) email.innerText = data.email || "—";
    if(role) role.innerText = data.role || "guest";
    if(auth) auth.innerText = data.auth_type || "anonymous";
    if(access) access.innerText = data.access_level || "—";

  }catch(e){

    console.error("Current user load error:", e);

  }

}

document.addEventListener("DOMContentLoaded", async () => {
  await loadSystemStatus();
  await loadUsers();
  await loadLog();
  await loadUsersCount();
  await loadIdeasStats();
  await loadCurrentUser();
});

  // ideas Overview
  
async function loadIdeasStats(){

  try{

    const r = await fetch("/api/admin/ideas_stats");
    const data = await r.json();

    const loading = document.getElementById("ideas_loading");
    const total = document.getElementById("ideas_total");
    const stats = document.getElementById("ideas_stats");
	const today = document.getElementById("ideas_today");
	const week = document.getElementById("ideas_week");
	const month = document.getElementById("ideas_month");

	if(today) today.innerText = data.today;
	if(week) week.innerText = data.week;
	if(month) month.innerText = data.month;

    if(loading)
        loading.style.display = "none";

    if(total)
        total.innerText = formatNumber(data.total);

    if(stats){

        let html = "";

        for(const key in data.stats){

            html += `<li><b>${key}</b>: ${data.stats[key]}</li>`;

        }

        stats.innerHTML = html;

    }

  }catch(e){

    console.error("Ideas stats error:", e);

  }

}

// Control users

async function loadCurrentUser(){

  try{

    const r = await fetch("/api/auth/me");
    const data = await r.json();

    const name = document.getElementById("currentUserName");
    const email = document.getElementById("currentUserEmail");
    const role = document.getElementById("currentUserRole");
    const auth = document.getElementById("currentUserAuth");
    const access = document.getElementById("currentUserAccess");

    if(name) name.innerText = data.name || "Guest";
    if(email) email.innerText = data.email || "—";
    if(role) role.innerText = data.role || "guest";
    if(auth) auth.innerText = data.auth_type || "anonymous";
    if(access) access.innerText = data.access_level || "—";

  }catch(e){

    console.error("Current user load error:", e);

  }

}

// выбор панели
function openPanel(){

  const select = document.getElementById("panelSelector");

  if(!select || !select.value){
    alert("Select panel first");
    return;
  }

  window.open(select.value, "_blank");

}