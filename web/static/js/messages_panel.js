/*
============================================================
Project: MindMesh
File: messages_panel.js
Version: 1.0
Date: 23.03.2026
Purpose:
Messages panel logic
============================================================
*/

document.addEventListener("DOMContentLoaded", async () => {
  await loadMessagesSummary();
  await loadMessagesList();
});

async function loadMessagesSummary(){

  try{

    const r = await fetch("/api/messages/unread_count");
    const data = await r.json();

    const el = document.getElementById("messages_total");
    if(el) el.innerText = data.count ?? 0;

  }catch(e){

    console.error("Messages summary error:", e);

  }

}

async function loadMessagesList(){

  try{

    const r = await fetch("/api/messages/list");
    const data = await r.json();

    const container = document.getElementById("messages-list");
    if(!container) return;

    if(!data.items || data.items.length === 0){
      container.innerHTML = "<div>No messages yet</div>";
      return;
    }

    let html = "";

    data.items.forEach(item => {
      html += `
        <div style="margin-bottom:10px; padding-bottom:8px; border-bottom:1px solid #333;">
          <div><b>${item.title}</b></div>
          <div style="opacity:0.8;">${item.preview}</div>
          <div style="font-size:12px; opacity:0.6;">${item.time}</div>
        </div>
      `;
    });

    container.innerHTML = html;

  }catch(e){

    console.error("Messages list error:", e);

  }

}

async function refreshMessages(){
  await loadMessagesSummary();
  await loadMessagesList();
}