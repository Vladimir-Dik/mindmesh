/*
============================================================
Project: MindMesh
File: topadmin_panel.js
Version: 1.0
Date: 22.03.2026
Purpose:
TopAdmin panel logic
============================================================
*/

document.addEventListener("DOMContentLoaded", async () => {

  await loadSystemStatus();
  await loadLog();
  await loadTopAdminStats();
  await loadTopAdminLog();

});

async function loadTopAdminStats(){

  try{

    const r1 = await fetch("/api/admin/users_count");
    const users = await r1.json();

    const usersEl = document.getElementById("topadmin_total_users");
    if(usersEl) usersEl.innerText = users.total_users ?? "-";

  }catch(e){
    console.error("TopAdmin users error:", e);
  }

  try{

    const r2 = await fetch("/api/admin/ideas_stats");
    const data = await r2.json();

    const total = document.getElementById("topadmin_total_ideas");
    const today = document.getElementById("topadmin_ideas_today");
    const week = document.getElementById("topadmin_ideas_week");
    const month = document.getElementById("topadmin_ideas_month");
    const stats = document.getElementById("topadmin_ideas_stats");
    const loading = document.getElementById("ideas_loading");

    if(loading) loading.style.display = "none";
    if(total) total.innerText = data.total ?? "-";
    if(today) today.innerText = data.today ?? "-";
    if(week) week.innerText = data.week ?? "-";
    if(month) month.innerText = data.month ?? "-";

    if(stats){
      let html = "";
      for(const key in data.stats){
        html += `<li><b>${key}</b>: ${data.stats[key]}</li>`;
      }
      stats.innerHTML = html;
    }

  }catch(e){
    console.error("TopAdmin ideas error:", e);
  }

}

async function loadTopAdminLog(){

  try{

    const r = await fetch("/api/system/log");
    const data = await r.json();

    const log = document.getElementById("topadmin-log");
    if(!log) return;

    let html = "";

    (data.log || []).slice(-10).reverse().forEach(entry => {
      html += `<div style="margin-bottom:4px;">▶ ${entry}</div>`;
    });

    log.innerHTML = html;

  }catch(e){
    console.error("TopAdmin log error:", e);
  }

}

function openUsersPanel() {
  window.location.href = "/user_management";
}


function openPanel() {
  const panel = document.getElementById("panelSelector").value;
  if (panel) {
    window.location.href = panel;
  }
}

/*function openUsersPanel(){
  window.open("/admin/users", "_blank");
}


function openPanel(){
  const select = document.getElementById("panelSelector");
  if(!select || !select.value) return;
  window.open(select.value, "_blank");
}*/