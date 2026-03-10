/*
Project: MindMesh
File: system_workdesk.js
Version: 1.1
Date: 2026-03-08
Purpose:
System Workdesk control script.

Functions:
- Load users list
- Load system log
- Toggle system modes
- Apply system configuration
*/

async function loadUsers() {

  const container = document.getElementById("users");
  if (!container) return;

  const res = await fetch("/api/admin/users");
  const data = await res.json();

  if (!data.users) return;

  let html = "<ul>";

  data.users.forEach(u => {
    html += `<li>${u.email} (${u.role})</li>`;
  });

  html += "</ul>";

  container.innerHTML = html;
}


async function loadLog() {

  const container = document.getElementById("system-log");
  if (!container) return;

  const res = await fetch("/api/system/log");
  const data = await res.json();

  if (!data.log) return;

  let html = "";

  data.log.forEach(entry => {
    html += `<div style="margin-bottom:4px;">▶ ${entry}</div>`;
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


document.addEventListener("DOMContentLoaded", async () => {

  await loadSystemStatus();
  await loadUsers();
  await loadLog();

});



async function loadSystemStatus() {

  const res = await fetch("/api/system/state");
  const data = await res.json();

  const test = document.getElementById("testModeStatus");
  const maint = document.getElementById("maintenanceStatus");

  if (!data) return;

  if (test)
    test.innerHTML = data.test_mode ? "ON" : "OFF";

  if (maint)
    maint.innerHTML = data.maintenance;

}