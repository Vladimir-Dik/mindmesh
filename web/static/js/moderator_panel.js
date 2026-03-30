/*
============================================================
Project: MindMesh
File: moderator_panel.js
Version: 1.0
Date: 22.03.2026
Purpose:
Moderator panel logic
============================================================
*/


document.addEventListener("DOMContentLoaded", async () => {

  await loadModeratorStats();
  await loadModeratorLog();
  await loadMessagesIndicator();

});

const data = { count: 2 };

async function loadModeratorStats(){

  try{

    const r1 = await fetch("/api/admin/users_count");
    const users = await r1.json();

    const usersEl = document.getElementById("moderator_total_users");
    if(usersEl) usersEl.innerText = users.total_users ?? "-";

  }catch(e){
    console.error("Moderator users error:", e);
  }

  try{

    const r2 = await fetch("/api/admin/ideas_stats");
    const data = await r2.json();

    const total = document.getElementById("moderator_total_ideas");
    const today = document.getElementById("moderator_ideas_today");
    const week = document.getElementById("moderator_ideas_week");
    const month = document.getElementById("moderator_ideas_month");
    const stats = document.getElementById("moderator_ideas_stats");
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
    console.error("Moderator ideas error:", e);
  }

}

async function loadModeratorLog(){

  try{

    const r = await fetch("/api/system/log");
    const data = await r.json();

    const log = document.getElementById("moderator-log");
    if(!log) return;

    let html = "";

    (data.log || []).slice(-10).reverse().forEach(entry => {
      html += `<div style="margin-bottom:4px;">▶ ${entry}</div>`;
    });

    log.innerHTML = html;

  }catch(e){
    console.error("Moderator log error:", e);
  }

}

function openUsersPanel(){
  window.open("/admin/users", "_blank");
}

function openPanel(){
  const select = document.getElementById("panelSelector");
  if(!select || !select.value) return;
  window.open(select.value, "_blank");
}




async function loadMessagesIndicator(){

  try{

    const r = await fetch("/api/messages/unread_count");

    if(!r.ok){
      console.warn("messages API not ready");
      return;
    }

    const data = await r.json();

    const countEl = document.getElementById("messages_count");
    const indicator = document.getElementById("messages_indicator");

    if(countEl)
      countEl.innerText = data.count ?? 0;

    if(indicator){

      if(data.count > 0){
        indicator.style.display = "inline";
        indicator.innerText = `● New (${data.count})`;
      }else{
        indicator.style.display = "none";
      }

    }

  }catch(e){

    console.error("Messages indicator error:", e);

  }

}

function openMessages(){
  window.open("/messages", "_blank");
}