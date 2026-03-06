async function loadUsers() {
  const res = await fetch("/api/admin/users");
  const data = await res.json();

  if (!data.users) return;

  let html = "<ul>";

  data.users.forEach(u => {
    html += `<li>${u.email} (${u.role})</li>`;
  });

  html += "</ul>";

  document.getElementById("userList").innerHTML = html;
}

async function loadLog() {
  const res = await fetch("/api/system/log");
  const data = await res.json();

  if (!data.log) return;

  let html = "";

  data.log.forEach(entry => {
    html += `<div>• ${entry}</div>`;
  });

  document.getElementById("systemLog").innerHTML = html;
}

async function toggleTest() {
  await fetch("/api/system/toggle-test", { method: "POST" });
  location.reload();
}

async function setSoft() {
  await fetch("/api/system/maintenance/soft", { method: "POST" });
  location.reload();
}

async function setFull() {
  await fetch("/api/system/maintenance/full", { method: "POST" });
  location.reload();
}

async function disableMaint() {
  await fetch("/api/system/maintenance/disable", { method: "POST" });
  location.reload();
}

document.addEventListener("DOMContentLoaded", () => {
  loadUsers();
  loadLog();
});
