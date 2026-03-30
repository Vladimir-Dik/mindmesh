/*
============================================================
Project: MindMesh
File: admin_panel.js
Version: 1.0
Date: 22.03.2026
Purpose:
Admin Panel logic
============================================================
*/

document.addEventListener("DOMContentLoaded", async () => {

  await loadAdminStats();
  await loadAdminUser();
  await loadAdminLog();

});

async function loadAdminStats(){

  try{

    const r = await fetch("/api/admin/ideas_stats");
    const data = await r.json();

    document.getElementById("admin_total_ideas").innerText = data.total;
    document.getElementById("admin_ideas_today").innerText = data.today;
    document.getElementById("admin_ideas_week").innerText = data.week;
    document.getElementById("admin_ideas_month").innerText = data.month;

    let html = "";

    for(const key in data.stats){
      html += `<li><b>${key}</b>: ${data.stats[key]}</li>`;
    }

    document.getElementById("admin_ideas_stats").innerHTML = html;

  }catch(e){
    console.error(e);
  }

  try{

    const r = await fetch("/api/admin/users_count");
    const data = await r.json();

    document.getElementById("admin_total_users").innerText = data.total_users;

  }catch(e){
    console.error(e);
  }

}

async function loadAdminUser(){

  try{

    const r = await fetch("/api/auth/me");
    const data = await r.json();

    if(data.role === "topadmin"){
      document.getElementById("topadmin_block").style.display = "block";
    }

  }catch(e){
    console.error(e);
  }

}

async function loadAdminLog(){

  try{

    const r = await fetch("/api/system/log");
    const data = await r.json();

    let html = "";

    data.log.slice(-5).reverse().forEach(e => {
      html += `<div>▶ ${e}</div>`;
    });

    document.getElementById("admin-log").innerHTML = html;

  }catch(e){
    console.error(e);
  }

}