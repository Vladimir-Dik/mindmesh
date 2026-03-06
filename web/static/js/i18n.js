/*
  MindMesh
  File: i18n.js
  Version: 2.0
  Date: 13.02.2026
  Purpose:
  - Modular language system
  - Dynamic JSON loading
  - Scalable architecture
*/

let currentLang = localStorage.getItem("lang") || "en";
let dictionary = {};

// ================= LOAD LANGUAGE =================

async function loadLanguage(lang) {
  try {
    const response = await fetch(`/static/i18n/${lang}.json?v=` + Date.now());
    if (!response.ok) throw new Error("Language file not found");

    dictionary = await response.json();
    currentLang = lang;
    localStorage.setItem("lang", lang);

    document.body.dir = (lang === "he") ? "rtl" : "ltr";

    applyTranslations();

    window.dispatchEvent(new Event("languageChanged"));

  } catch (err) {
    console.error("i18n load error:", err);
  }
}

// ================= TRANSLATION FUNCTION =================

function t(key) {
  return dictionary[key] || key;
}

// ================= APPLY =================

function applyTranslations() {

  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.getAttribute("data-i18n");
    el.textContent = t(key);
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
    const key = el.getAttribute("data-i18n-placeholder");
    el.setAttribute("placeholder", t(key));
  });

}


// ================= INIT =================

document.addEventListener("DOMContentLoaded", function () {
  loadLanguage(currentLang);
});

// ================= PUBLIC API =================

function setLanguage(lang) {
  loadLanguage(lang);
}

console.log("MindMesh i18n v2.0 loaded");
