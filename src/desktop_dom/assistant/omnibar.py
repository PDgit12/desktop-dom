from __future__ import annotations
import sys
import json
import time
import logging
import threading
from typing import Optional, Dict, Any

logger = logging.getLogger("desktop_dom.assistant.omnibar")

OMNIBAR_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    user-select: none;
    -webkit-user-select: none;
  }
  input, textarea {
    user-select: text !important;
    -webkit-user-select: text !important;
  }
  body {
    width: 100vw;
    height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    background: transparent;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", sans-serif;
    overflow: hidden;
  }
  .omnibar-card {
    width: 680px;
    border-radius: 12px;
    background: rgba(22, 22, 24, 0.96);
    backdrop-filter: blur(40px) saturate(190%);
    -webkit-backdrop-filter: blur(40px) saturate(190%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 24px 64px rgba(0, 0, 0, 0.7), inset 0 1px 0 rgba(255, 255, 255, 0.06);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: border-color 0.15s ease;
  }
  .omnibar-card.executing {
    border-color: rgba(255, 255, 255, 0.16);
  }
  .header-bar {
    height: 52px;
    display: flex;
    align-items: center;
    padding: 0 16px;
    gap: 12px;
    position: relative;
  }
  .search-icon {
    width: 16px;
    height: 16px;
    color: #71717a;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .input-wrap {
    flex: 1;
    display: flex;
    align-items: center;
    cursor: text;
  }
  input#query-input {
    width: 100%;
    background: transparent;
    border: none;
    outline: none;
    color: #f4f4f5;
    font-size: 15px;
    font-weight: 450;
    letter-spacing: -0.15px;
    user-select: text !important;
    -webkit-user-select: text !important;
    cursor: text;
  }
  input#query-input::placeholder {
    color: #52525b;
    font-weight: 400;
  }
  .header-tools {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  .model-pill-btn {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 3px 8px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    font-size: 11px;
    font-weight: 500;
    color: #a1a1aa;
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .model-pill-btn:hover {
    background: rgba(255, 255, 255, 0.08);
    color: #f4f4f5;
    border-color: rgba(255, 255, 255, 0.14);
  }
  .chevron {
    color: #71717a;
    font-size: 9px;
  }
  .mic-btn {
    width: 26px;
    height: 26px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.12s ease;
    color: #71717a;
  }
  .mic-btn:hover {
    background: rgba(255, 255, 255, 0.08);
    color: #f4f4f5;
  }
  .mic-btn.active {
    background: rgba(239, 68, 68, 0.15);
    border-color: rgba(239, 68, 68, 0.4);
    color: #ef4444;
  }
  .status-badge {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 500;
    color: #71717a;
    letter-spacing: 0.2px;
  }
  .status-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #38bdf8;
  }
  .progress-line {
    height: 1px;
    width: 100%;
    background: rgba(255, 255, 255, 0.06);
    position: relative;
    overflow: hidden;
  }
  .progress-line.active::after {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    width: 30%;
    background: linear-gradient(90deg, transparent, #38bdf8, transparent);
    animation: progressSlide 1.1s infinite cubic-bezier(0.4, 0, 0.2, 1);
  }
  @keyframes progressSlide {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(350%); }
  }
  .section-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #71717a;
    padding: 8px 14px 4px 14px;
  }
  .tray {
    display: flex;
    flex-direction: column;
    padding: 2px 6px 6px 6px;
    max-height: 250px;
    overflow-y: auto;
  }
  .suggestion-item {
    display: flex;
    align-items: center;
    padding: 0 10px;
    height: 38px;
    border-radius: 6px;
    gap: 10px;
    cursor: pointer;
    transition: background 0.08s ease;
  }
  .suggestion-item:hover, .suggestion-item.selected {
    background: rgba(255, 255, 255, 0.06);
  }
  .suggestion-icon {
    width: 16px;
    height: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #71717a;
    flex-shrink: 0;
  }
  .suggestion-item.selected .suggestion-icon {
    color: #f4f4f5;
  }
  .suggestion-content {
    flex: 1;
    display: flex;
    align-items: baseline;
    gap: 8px;
    min-width: 0;
  }
  .suggestion-title {
    color: #e4e4e7;
    font-size: 13px;
    font-weight: 450;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .suggestion-item.selected .suggestion-title {
    color: #ffffff;
  }
  .suggestion-subtitle {
    color: #71717a;
    font-size: 11.5px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .suggestion-badge {
    font-size: 9.5px;
    font-weight: 500;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    padding: 2px 6px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    color: #71717a;
    letter-spacing: 0.2px;
    text-transform: uppercase;
  }
  .suggestion-item.selected .suggestion-badge {
    color: #a1a1aa;
    border-color: rgba(255, 255, 255, 0.12);
  }

  /* Raycast-Style Result Detail View */
  .result-drawer {
    display: none;
    flex-direction: column;
    padding: 14px 18px;
    gap: 12px;
    max-height: 260px;
    overflow-y: auto;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
  }
  .result-drawer.visible {
    display: flex;
  }
  .result-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .result-pills {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .pill {
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.2px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .pill-success {
    background: rgba(52, 211, 153, 0.1);
    color: #34d399;
    border: 1px solid rgba(52, 211, 153, 0.2);
  }
  .pill-engine {
    background: rgba(255, 255, 255, 0.04);
    color: #a1a1aa;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .result-actions {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .action-btn {
    padding: 3px 9px;
    border-radius: 5px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #a1a1aa;
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .action-btn:hover {
    background: rgba(255, 255, 255, 0.08);
    color: #f4f4f5;
  }
  .action-btn.active {
    background: rgba(255, 255, 255, 0.14);
    color: #ffffff;
  }
  .result-body {
    color: #e4e4e7;
    font-size: 13.5px;
    line-height: 1.6;
    white-space: pre-wrap;
    user-select: text;
    -webkit-user-select: text;
    word-break: break-word;
  }
  .result-math-highlight {
    font-size: 28px;
    font-weight: 600;
    color: #ffffff;
    letter-spacing: -0.5px;
    margin-bottom: 2px;
  }
  .result-math-sub {
    font-size: 12px;
    color: #71717a;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  /* Minimalist Model Switcher */
  .model-drawer {
    display: none;
    flex-direction: column;
    padding: 10px 14px;
    gap: 4px;
    max-height: 240px;
    overflow-y: auto;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
  }
  .model-drawer.visible {
    display: flex;
  }
  .model-drawer-title {
    font-size: 10px;
    font-weight: 600;
    color: #71717a;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 6px 8px 6px;
  }
  .model-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 10px;
    border-radius: 6px;
    background: transparent;
    border: 1px solid transparent;
    cursor: pointer;
    transition: all 0.1s ease;
  }
  .model-card:hover {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.08);
  }
  .model-card.active {
    background: rgba(255, 255, 255, 0.07);
    border-color: rgba(255, 255, 255, 0.12);
  }
  .model-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .model-name {
    color: #e4e4e7;
    font-size: 13px;
    font-weight: 500;
  }
  .model-card.active .model-name {
    color: #ffffff;
  }
  .model-desc {
    color: #71717a;
    font-size: 11px;
  }
  .check-icon {
    width: 14px;
    height: 14px;
    color: #34d399;
    display: none;
  }
  .model-card.active .check-icon {
    display: block;
  }

  .footer-bar {
    height: 32px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 14px;
    font-size: 10.5px;
    color: #71717a;
  }
  .shortcuts {
    display: flex;
    gap: 12px;
    align-items: center;
  }
  .kbd-pill {
    display: inline-flex;
    align-items: center;
    gap: 3px;
  }
  .kbd {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 3px;
    padding: 0 4px;
    font-size: 9px;
    font-weight: 500;
    color: #a1a1aa;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .local-tag {
    display: flex;
    align-items: center;
    gap: 5px;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
    transition: background 0.1s ease;
    color: #71717a;
  }
  .local-tag:hover {
    background: rgba(255, 255, 255, 0.05);
    color: #a1a1aa;
  }
  .dot-green {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #10b981;
  }
  .dot-amber {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #f59e0b;
  }
</style>
</head>
<body>
  <div class="omnibar-card" id="card">
    <div class="header-bar" id="header-bar">
      <div class="search-icon">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/>
          <line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      </div>
      <div class="input-wrap">
        <input id="query-input" type="text" placeholder="Search commands or ask Aura..." autocomplete="off" spellcheck="false" autofocus />
      </div>
      <div class="header-tools">
        <div class="model-pill-btn" id="model-pill" title="Active Engine / Switch Models">
          <span id="header-model-name">Fast-Path</span>
          <span class="chevron">▾</span>
        </div>
        <div class="mic-btn" id="mic-btn" title="Toggle Voice Microphone">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="22"/>
          </svg>
        </div>
        <div class="status-badge" id="badge">
          <span class="status-dot" id="status-dot"></span>
          <span id="badge-text">Ready</span>
        </div>
      </div>
    </div>

    <div class="progress-line" id="progress"></div>

    <div id="command-section">
      <div class="section-label" id="section-label">Commands</div>
      <div class="tray" id="tray">
        <!-- Dynamically generated suggestions -->
      </div>
    </div>

    <div class="result-drawer" id="result-drawer">
      <div class="result-header">
        <div class="result-pills">
          <span class="pill pill-success" id="result-status-pill">Completed</span>
          <span class="pill pill-engine" id="result-engine-pill">Fast-Path · 12ms</span>
        </div>
        <div class="result-actions">
          <button class="action-btn" id="copy-btn">Copy</button>
          <button class="action-btn" id="done-btn">Done (Esc)</button>
        </div>
      </div>
      <div class="result-body" id="result-body"></div>
    </div>

    <div class="model-drawer" id="model-drawer">
      <div class="model-drawer-title">
        <span>Active Engine & Local Models</span>
        <span id="model-conn-status">Checking...</span>
      </div>
      <div id="model-list" style="display: flex; flex-direction: column; gap: 2px;">
        <!-- Dynamically rendered models -->
      </div>
    </div>

    <div class="footer-bar">
      <div class="shortcuts">
        <span class="kbd-pill"><span class="kbd">↵</span> Run</span>
        <span class="kbd-pill"><span class="kbd">↑↓</span> Navigate</span>
        <span class="kbd-pill"><span class="kbd">Tab</span> Fill</span>
        <span class="kbd-pill"><span class="kbd">Esc</span> Dismiss</span>
      </div>
      <div class="local-tag" id="footer-model-tag" title="Switch local AI engines">
        <div class="dot-green" id="model-dot"></div>
        <span id="footer-model-name">Loading...</span>
      </div>
    </div>
  </div>

  <script>
    const input = document.getElementById("query-input");
    const card = document.getElementById("card");
    const badgeText = document.getElementById("badge-text");
    const statusDot = document.getElementById("status-dot");
    const micBtn = document.getElementById("mic-btn");
    const tray = document.getElementById("tray");
    const progress = document.getElementById("progress");
    const commandSection = document.getElementById("command-section");
    const resultDrawer = document.getElementById("result-drawer");
    const resultBody = document.getElementById("result-body");
    const resultStatusPill = document.getElementById("result-status-pill");
    const resultEnginePill = document.getElementById("result-engine-pill");
    const copyBtn = document.getElementById("copy-btn");
    const doneBtn = document.getElementById("done-btn");
    const modelDrawer = document.getElementById("model-drawer");
    const modelList = document.getElementById("model-list");
    const modelConnStatus = document.getElementById("model-conn-status");
    const modelPill = document.getElementById("model-pill");
    const headerModelName = document.getElementById("header-model-name");
    const footerModelTag = document.getElementById("footer-model-tag");
    const footerModelName = document.getElementById("footer-model-name");
    const modelDot = document.getElementById("model-dot");

    // Pure Monochrome Vector SVGs (Zero Emojis)
    const ICONS = {
      search: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
      math: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/></svg>',
      media: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
      volume: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>',
      app: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
      screen: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
      model: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><circle cx="19" cy="6" r="2"/><circle cx="5" cy="6" r="2"/><circle cx="19" cy="18" r="2"/><circle cx="5" cy="18" r="2"/><line x1="12" y1="9" x2="12" y2="3"/><line x1="12" y1="15" x2="12" y2="21"/><line x1="9.5" y1="10.5" x2="6.5" y2="7.5"/><line x1="14.5" y1="10.5" x2="17.5" y2="7.5"/></svg>',
      check: '<svg class="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
    };

    let isListening = false;
    let selectedIndex = 0;
    let currentSuggestions = [];
    let currentResultRaw = "";
    let autoCloseTimer = null;
    let isDrawerOpen = false;

    const defaultActions = [
      { iconType: "media", title: "Play Spotify", subtitle: "Play Starboy on Spotify", query: "Play Starboy on Spotify", badge: "Fast-Path" },
      { iconType: "math", title: "Calculate Expression", subtitle: "Calculate 125 * 40 + 15", query: "Calculate 125 * 40 + 15", badge: "AST" },
      { iconType: "volume", title: "Adjust Volume", subtitle: "Set volume to 80%", query: "Set volume to 80", badge: "System" },
      { iconType: "app", title: "Activate Application", subtitle: "Open Calculator", query: "Open Calculator", badge: "App" },
      { iconType: "screen", title: "Inspect Screen", subtitle: "What is on my screen?", query: "what is on my screen", badge: "DOM" },
      { iconType: "model", title: "Switch AI Engine", subtitle: "View local neural weights", query: "/model", badge: "Engine" }
    ];

    function updateSuggestions() {
      if (isDrawerOpen) return;
      const q = input.value.trim();
      currentSuggestions = [];

      if (!q) {
        currentSuggestions = defaultActions;
      } else {
        if (q.startsWith("/model") || q === "models" || q === "status") {
          currentSuggestions.push({
            iconType: "model",
            title: "Manage AI Models",
            subtitle: "View local Ollama neural weights & zero-model fast path",
            query: "/model",
            badge: "Engine"
          });
        }

        const mathClean = q.replace(/[^0-9+*/.() -]/g, "").trim();
        if (mathClean && /[+*/-]/.test(mathClean) && !mathClean.includes("**")) {
          try {
            const evaluated = Function('"use strict";return (' + mathClean + ')')();
            if (typeof evaluated === "number" && isFinite(evaluated)) {
              currentSuggestions.push({
                iconType: "math",
                title: `= ${evaluated.toLocaleString()}`,
                subtitle: `Calculate ${mathClean}`,
                query: q,
                badge: "Math"
              });
            }
          } catch(e) {}
        }

        if (q.toLowerCase().startsWith("play ") || q.toLowerCase().includes("spotify")) {
          currentSuggestions.push({
            iconType: "media",
            title: `Play "${q.replace(/play/i, "").replace(/on spotify/i, "").trim()}"`,
            subtitle: "Spotify Media Controller (<120ms)",
            query: q,
            badge: "Spotify"
          });
        }

        if (q.toLowerCase().includes("volume") || q.toLowerCase().includes("mute")) {
          currentSuggestions.push({
            iconType: "volume",
            title: q,
            subtitle: "System Audio Hardware Bus (<30ms)",
            query: q,
            badge: "System"
          });
        }

        if (q.toLowerCase().startsWith("open ") || q.toLowerCase().startsWith("launch ")) {
          const appName = q.replace(/^(open|launch)\s+/i, "").trim();
          currentSuggestions.push({
            iconType: "app",
            title: `Activate ${appName}`,
            subtitle: "DesktopApp Window Attachment (<80ms)",
            query: q,
            badge: "App"
          });
        }

        if (q.toLowerCase().includes("screen") || q.toLowerCase().includes("window")) {
          currentSuggestions.push({
            iconType: "screen",
            title: "Inspect Active Screen & Hierarchy",
            subtitle: "Sub-50ms deterministic accessibility tree extraction",
            query: q,
            badge: "DOM"
          });
        }

        currentSuggestions.push({
          iconType: "search",
          title: `Ask Aura: "${q}"`,
          subtitle: "Local Ollama ReAct Planning Loop",
          query: q,
          badge: "Ollama"
        });
      }

      renderSuggestions();
    }

    function renderSuggestions() {
      tray.innerHTML = "";
      commandSection.style.display = "block";
      resultDrawer.classList.remove("visible");
      modelDrawer.classList.remove("visible");
      isDrawerOpen = false;

      if (selectedIndex >= currentSuggestions.length) {
        selectedIndex = 0;
      }

      currentSuggestions.forEach((item, idx) => {
        const el = document.createElement("div");
        el.className = "suggestion-item" + (idx === selectedIndex ? " selected" : "");
        const iconSvg = ICONS[item.iconType] || ICONS.search;
        el.innerHTML = `
          <div class="suggestion-icon">${iconSvg}</div>
          <div class="suggestion-content">
            <span class="suggestion-title">${escapeHtml(item.title)}</span>
            <span class="suggestion-subtitle">${escapeHtml(item.subtitle)}</span>
          </div>
          <div class="suggestion-badge">${escapeHtml(item.badge)}</div>
        `;
        el.addEventListener("click", () => {
          submitQuery(item.query);
        });
        tray.appendChild(el);
      });

      notifyResize();
    }

    let lastReportedHeight = 0;
    function notifyResize() {
      let contentHeight = 52 + 32 + 16;
      if (resultDrawer.classList.contains("visible")) {
        contentHeight = 52 + resultDrawer.scrollHeight + 32 + 16;
      } else if (modelDrawer.classList.contains("visible")) {
        contentHeight = 52 + modelDrawer.scrollHeight + 32 + 16;
      } else {
        contentHeight = 52 + 24 + (currentSuggestions.length * 38) + 32 + 12;
      }
      const targetHeight = Math.min(420, Math.max(80, contentHeight));
      if (Math.abs(targetHeight - lastReportedHeight) < 4) {
        return;
      }
      lastReportedHeight = targetHeight;
      window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
        action: "resize",
        height: targetHeight
      }));
    }

    window.resetOmnibar = function() {
      if (autoCloseTimer) clearTimeout(autoCloseTimer);
      resultDrawer.classList.remove("visible");
      modelDrawer.classList.remove("visible");
      commandSection.style.display = "block";
      isDrawerOpen = false;
      badgeText.innerText = "Ready";
      statusDot.style.background = "#38bdf8";
      card.classList.remove("executing");
      progress.classList.remove("active");
      input.value = "";
      selectedIndex = 0;
      updateSuggestions();
      input.focus();
    };

    function escapeHtml(str) {
      return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    input.addEventListener("input", () => {
      selectedIndex = 0;
      updateSuggestions();
    });

    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (!isDrawerOpen && currentSuggestions.length > 0) {
          selectedIndex = (selectedIndex + 1) % currentSuggestions.length;
          renderSuggestions();
        }
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (!isDrawerOpen && currentSuggestions.length > 0) {
          selectedIndex = (selectedIndex - 1 + currentSuggestions.length) % currentSuggestions.length;
          renderSuggestions();
        }
      } else if (e.key === "Tab") {
        e.preventDefault();
        if (!isDrawerOpen && currentSuggestions[selectedIndex]) {
          input.value = currentSuggestions[selectedIndex].query;
          updateSuggestions();
        }
      } else if (e.key === "Enter") {
        if (isDrawerOpen) {
          closeDrawers();
        } else {
          const item = currentSuggestions[selectedIndex];
          const val = item ? item.query : input.value.trim();
          if (val) submitQuery(val);
        }
      } else if (e.key === "Escape") {
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "close" }));
      }
    });

    micBtn.addEventListener("click", toggleMic);
    modelPill.addEventListener("click", toggleModelDrawer);
    footerModelTag.addEventListener("click", toggleModelDrawer);

    copyBtn.addEventListener("click", () => {
      if (currentResultRaw) {
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
          action: "copy_to_clipboard",
          text: currentResultRaw
        }));
        copyBtn.innerText = "Copied";
        copyBtn.classList.add("active");
        setTimeout(() => {
          copyBtn.innerText = "Copy";
          copyBtn.classList.remove("active");
        }, 1400);
      }
    });

    doneBtn.addEventListener("click", closeDrawers);

    function closeDrawers() {
      if (autoCloseTimer) clearTimeout(autoCloseTimer);
      resultDrawer.classList.remove("visible");
      modelDrawer.classList.remove("visible");
      commandSection.style.display = "block";
      isDrawerOpen = false;
      badgeText.innerText = "Ready";
      statusDot.style.background = "#38bdf8";
      card.classList.remove("executing");
      updateSuggestions();
      input.focus();
    }

    function toggleMic() {
      isListening = !isListening;
      if (isListening) {
        micBtn.classList.add("active");
        badgeText.innerText = "Listening";
        statusDot.style.background = "#ef4444";
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "start_listening" }));
      } else {
        micBtn.classList.remove("active");
        badgeText.innerText = "Ready";
        statusDot.style.background = "#38bdf8";
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "stop_listening" }));
      }
    }

    function submitQuery(query) {
      if (autoCloseTimer) clearTimeout(autoCloseTimer);
      card.classList.add("executing");
      badgeText.innerText = "Running";
      statusDot.style.background = "#10b981";
      progress.classList.add("active");

      window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
        action: "submit_query",
        query: query
      }));
    }

    function toggleModelDrawer() {
      if (modelDrawer.classList.contains("visible")) {
        closeDrawers();
      } else {
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "get_model_status" }));
      }
    }

    window.displayResult = function(payload) {
      progress.classList.remove("active");
      card.classList.remove("executing");
      commandSection.style.display = "none";
      modelDrawer.classList.remove("visible");
      resultDrawer.classList.add("visible");
      isDrawerOpen = true;

      const respText = payload.response || "Completed successfully.";
      currentResultRaw = respText;

      const action = payload.action || "";
      if (action === "calculate" && payload.result) {
        resultBody.innerHTML = `
          <div class="result-math-highlight">${escapeHtml(payload.result)}</div>
          <div class="result-math-sub">${escapeHtml(payload.expression || "")}</div>
        `;
      } else {
        resultBody.innerText = respText;
      }

      const engine = payload.engine || "fast_path";
      const latency = payload.latency_ms ? `${Math.round(payload.latency_ms)}ms` : "";

      if (engine === "fast_path") {
        resultEnginePill.innerText = latency ? `Fast-Path · ${latency}` : "Fast-Path";
      } else if (engine === "ollama") {
        resultEnginePill.innerText = latency ? `Ollama · ${latency}` : "Ollama";
      } else {
        resultEnginePill.innerText = latency ? `Done · ${latency}` : "Done";
      }

      badgeText.innerText = "Done";
      statusDot.style.background = "#10b981";

      notifyResize();

      const bgActions = [
        "open_app", "spotify_play", "spotify_playpause", "spotify_next track",
        "set_volume", "volume_up", "volume_down", "mute", "unmute",
        "create_note", "copy_clipboard", "web_search", "screenshot",
        "toggle_dark_mode", "window_minimize", "window_maximize", "window_close",
        "click", "type", "press"
      ];
      if (bgActions.includes(action)) {
        const delay = action === "open_app" ? 350 : 700;
        autoCloseTimer = setTimeout(() => {
          window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "close" }));
        }, delay);
      }
    };

    window.displayModelDrawer = function(status) {
      progress.classList.remove("active");
      commandSection.style.display = "none";
      resultDrawer.classList.remove("visible");
      modelDrawer.classList.add("visible");
      isDrawerOpen = true;

      const isConn = status.connected;
      const current = status.current_model || "Zero-Model Fast-Path";
      const models = status.available_models || [];

      modelConnStatus.innerHTML = isConn 
        ? `<span style="color:#10b981">Connected (${status.latency_ms}ms)</span>`
        : `<span style="color:#f59e0b">Offline (Fast-Path Only)</span>`;

      modelList.innerHTML = "";

      const fpCard = document.createElement("div");
      fpCard.className = "model-card" + (current === "Zero-Model Fast-Path" ? " active" : "");
      fpCard.innerHTML = `
        <div class="model-info">
          <div class="model-name">Zero-Model Fast-Path</div>
          <div class="model-desc">Sub-25ms deterministic AST & AppleScript dispatch (0MB RAM)</div>
        </div>
        ${ICONS.check}
      `;
      fpCard.addEventListener("click", () => {
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
          action: "set_model",
          model: "Zero-Model Fast-Path"
        }));
      });
      modelList.appendChild(fpCard);

      models.forEach(m => {
        const isAct = (current === m);
        const cardEl = document.createElement("div");
        cardEl.className = "model-card" + (isAct ? " active" : "");
        cardEl.innerHTML = `
          <div class="model-info">
            <div class="model-name">${escapeHtml(m)}</div>
            <div class="model-desc">Local neural reasoning model (localhost:11434)</div>
          </div>
          ${ICONS.check}
        `;
        cardEl.addEventListener("click", () => {
          window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
            action: "set_model",
            model: m
          }));
        });
        modelList.appendChild(cardEl);
      });

      notifyResize();
    };

    window.updateModelStatus = function(status) {
      if (!status) return;
      const cur = status.current_model || "Zero-Model Fast-Path";
      const shortName = cur.includes(":") ? cur.split(":")[0] : cur;
      headerModelName.innerText = shortName.length > 18 ? shortName.slice(0, 16) + "…" : shortName;
      footerModelName.innerText = cur.length > 24 ? cur.slice(0, 22) + "…" : cur;
      if (status.connected) {
        modelDot.className = "dot-green";
      } else {
        modelDot.className = "dot-amber";
      }
    };

    updateSuggestions();
    input.focus();

    card.addEventListener("click", (e) => {
      if (!e.target.closest("#mic-btn") && !e.target.closest(".action-btn") && !e.target.closest("#footer-model-tag") && !e.target.closest("#model-pill") && !e.target.closest(".model-card")) {
        input.focus();
      }
    });

    window.addEventListener("focus", () => {
      setTimeout(() => input.focus(), 30);
    });

    window.addEventListener("DOMContentLoaded", () => {
      input.focus();
    });

    setTimeout(() => {
      input.focus();
      window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "get_model_status" }));
    }, 120);
  </script>
</body>
</html>
"""

class OmnibarScriptHandler:
    def __init__(self, omnibar_controller):
        self.controller = omnibar_controller

    def userContentController_didReceiveScriptMessage_(self, ucc, msg):
        try:
            payload = json.loads(str(msg.body()))
            action = payload.get("action")
            if action == "submit_query":
                query = payload.get("query", "")
                self.controller.on_query_submitted(query)
            elif action == "start_listening":
                self.controller.on_voice_requested()
            elif action == "stop_listening":
                if self.controller.audio:
                    self.controller.audio.stop_speaking()
            elif action == "resize":
                new_h = float(payload.get("height", 80))
                self.controller.resize_window(new_h)
            elif action == "close":
                self.controller.hide()
            elif action == "get_model_status":
                self.controller.on_model_status_requested()
            elif action == "set_model":
                model_name = payload.get("model", "")
                self.controller.on_model_switch(model_name)
            elif action == "copy_to_clipboard":
                text = payload.get("text", "")
                self.controller.copy_text(text)
        except Exception as e:
            logger.warning(f"Error handling script message: {e}")

class FloatingOmnibar:
    """
    Native macOS floating minimalist spotlight bar powered by Cocoa & WebKit.
    Floats on top of all windows and spaces on hotkey (Cmd+Shift+Space),
    with dynamic height expansion, multi-display mouse tracking, and menubar status item.
    """

    def __init__(self, brain=None, audio=None):
        self.brain = brain
        self.audio = audio
        self._panel = None
        self._webview = None
        self._app = None
        self._status_item = None
        self._menu_delegate = None
        self._is_visible = False
        self._base_width = 720
        self._base_height = 360

    def dispatch_main(self, fn):
        """Safely dispatches a callable to the macOS main UI thread."""
        if threading.current_thread() is threading.main_thread():
            fn()
            return
        try:
            import Cocoa
            app = Cocoa.NSApplication.sharedApplication()
            if app and app.isRunning():
                Cocoa.NSOperationQueue.mainQueue().addOperationWithBlock_(fn)
            else:
                fn()
        except Exception:
            fn()

    def evaluate_js(self, js_code: str):
        """Evaluates JavaScript inside the WKWebView on the main thread."""
        if not self._webview:
            return
        def _do():
            try:
                self._webview.evaluateJavaScript_completionHandler_(js_code, None)
            except Exception as e:
                logger.debug(f"JS eval error: {e}")
        self.dispatch_main(_do)

    def setup_ui(self):
        """Initializes the Cocoa window, WebKit view, and status bar item."""
        try:
            import Cocoa
            import WebKit
            import objc
        except ImportError:
            raise RuntimeError("PyObjC Cocoa and WebKit required for native Omnibar.")

        self._app = Cocoa.NSApplication.sharedApplication()
        self._app.setActivationPolicy_(Cocoa.NSApplicationActivationPolicyAccessory)

        screen = Cocoa.NSScreen.mainScreen()
        if screen is None:
            raise RuntimeError("No active display screen found for Cocoa GUI.")
        screen_frame = screen.frame()
        bar_width = self._base_width
        bar_height = self._base_height
        pos_x = (screen_frame.size.width - bar_width) / 2
        pos_y = screen_frame.size.height * 0.58

        # Create frameless floating KeyablePanel capable of accepting keyboard focus
        try:
            panel_cls = objc.lookUpClass("AuraKeyablePanelObjC")
        except Exception:
            panel_cls = None

        if panel_cls is None:
            class AuraKeyablePanelObjC(Cocoa.NSPanel):
                def canBecomeKeyWindow(self):
                    return True

                def canBecomeMainWindow(self):
                    return True

                def needsPanelToBecomeKey(self):
                    return True

                def acceptsFirstResponder(self):
                    return True

            panel_cls = AuraKeyablePanelObjC

        self._panel = panel_cls.alloc().initWithContentRect_styleMask_backing_defer_(
            Cocoa.NSMakeRect(pos_x, pos_y, bar_width, bar_height),
            Cocoa.NSWindowStyleMaskBorderless,
            Cocoa.NSBackingStoreBuffered,
            False,
        )

        self._panel.setLevel_(Cocoa.NSFloatingWindowLevel)
        self._panel.setOpaque_(False)
        self._panel.setBackgroundColor_(Cocoa.NSColor.clearColor())
        self._panel.setHasShadow_(False)
        self._panel.setMovableByWindowBackground_(True)
        self._panel.setBecomesKeyOnlyIfNeeded_(False)
        self._panel.setWorksWhenModal_(True)
        self._panel.setHidesOnDeactivate_(False)
        self._panel.setAcceptsMouseMovedEvents_(True)
        self._panel.setCollectionBehavior_(
            Cocoa.NSWindowCollectionBehaviorCanJoinAllSpaces |
            Cocoa.NSWindowCollectionBehaviorFullScreenAuxiliary
        )

        # Panel Delegate for auto-hiding when clicking outside with grace period
        try:
            panel_del_cls = objc.lookUpClass("AuraPanelDelegateObjC")
        except Exception:
            panel_del_cls = None

        if panel_del_cls is None:
            class AuraPanelDelegateObjC(Cocoa.NSObject):
                def initWithController_(self, ctrl):
                    self = objc.super(AuraPanelDelegateObjC, self).init()
                    if self:
                        self.ctrl = ctrl
                    return self

                def windowDidResignKey_(self, notification):
                    if self.ctrl and getattr(self.ctrl, "_is_visible", False):
                        if time.time() - getattr(self.ctrl, "_show_time", 0) < 0.6:
                            return
                        self.ctrl.hide()

            panel_del_cls = AuraPanelDelegateObjC

        self._panel_delegate = panel_del_cls.alloc().initWithController_(self)
        self._panel.setDelegate_(self._panel_delegate)
        self._setup_click_outside_monitor()

        # Configure WebKit View
        config = WebKit.WKWebViewConfiguration.alloc().init()
        
        # Script Message Handler Bridge
        try:
            handler_cls = objc.lookUpClass("OmnibarScriptHandlerObjC")
        except Exception:
            handler_cls = None

        if handler_cls is None:
            class OmnibarScriptHandlerObjC(Cocoa.NSObject):
                def initWithController_(self, ctrl):
                    self = objc.super(OmnibarScriptHandlerObjC, self).init()
                    if self:
                        self.ctrl = ctrl
                    return self

                def userContentController_didReceiveScriptMessage_(self, ucc, msg):
                    try:
                        payload = json.loads(str(msg.body()))
                        act = payload.get("action")
                        if act == "submit_query":
                            self.ctrl.on_query_submitted(payload.get("query", ""))
                        elif act == "start_listening":
                            self.ctrl.on_voice_requested()
                        elif act == "stop_listening":
                            if self.ctrl.audio:
                                self.ctrl.audio.stop_speaking()
                        elif act == "resize":
                            new_h = float(payload.get("height", 80))
                            self.ctrl.resize_window(new_h)
                        elif act == "close":
                            self.ctrl.hide()
                        elif act == "get_model_status":
                            self.ctrl.on_model_status_requested()
                        elif act == "set_model":
                            self.ctrl.on_model_switch(payload.get("model", ""))
                        elif act == "copy_to_clipboard":
                            self.ctrl.copy_text(payload.get("text", ""))
                    except Exception as e:
                        logger.warning(f"Bridge dispatch error: {e}")

            handler_cls = OmnibarScriptHandlerObjC

        handler_obj = handler_cls.alloc().initWithController_(self)
        config.userContentController().addScriptMessageHandler_name_(handler_obj, "desktopDom")

        self._webview = WebKit.WKWebView.alloc().initWithFrame_configuration_(
            Cocoa.NSMakeRect(0, 0, bar_width, bar_height),
            config
        )
        self._webview.setValue_forKey_(False, "drawsBackground")
        self._webview.loadHTMLString_baseURL_(OMNIBAR_HTML, None)

        self._panel.contentView().addSubview_(self._webview)
        self.setup_status_item()

    def setup_status_item(self):
        """Sets up a sleek native macOS menu bar status item."""
        try:
            import Cocoa
            import objc
            status_bar = Cocoa.NSStatusBar.systemStatusBar()
            self._status_item = status_bar.statusItemWithLength_(Cocoa.NSVariableStatusItemLength)
            btn = self._status_item.button()
            if btn:
                btn.setTitle_("◇")
                btn.setToolTip_("Aura (Cmd+Shift+Space)")

            try:
                del_cls = objc.lookUpClass("AuraMenuDelegateObjC")
            except Exception:
                del_cls = None

            if del_cls is None:
                class AuraMenuDelegateObjC(Cocoa.NSObject):
                    def initWithController_(self, ctrl):
                        self = objc.super(AuraMenuDelegateObjC, self).init()
                        if self:
                            self.ctrl = ctrl
                        return self

                    def onMenuShow_(self, sender):
                        if self.ctrl:
                            self.ctrl.show()

                    def onMenuQuit_(self, sender):
                        if self.ctrl and self.ctrl._app:
                            self.ctrl._app.stop_(None)
                        sys.exit(0)

                del_cls = AuraMenuDelegateObjC

            self._menu_delegate = del_cls.alloc().initWithController_(self)
            menu = Cocoa.NSMenu.alloc().init()

            item_show = Cocoa.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Show Aura (Cmd+Shift+Space)", "onMenuShow:", ""
            )
            item_show.setTarget_(self._menu_delegate)
            menu.addItem_(item_show)

            menu.addItem_(Cocoa.NSMenuItem.separatorItem())

            model_name = getattr(self.brain, "preferred_model", None) or "Fast-Path Engine"
            item_model = Cocoa.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                f"Model: {model_name}", "", ""
            )
            item_model.setEnabled_(False)
            menu.addItem_(item_model)

            menu.addItem_(Cocoa.NSMenuItem.separatorItem())

            item_quit = Cocoa.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Quit Aura", "onMenuQuit:", "q"
            )
            item_quit.setTarget_(self._menu_delegate)
            menu.addItem_(item_quit)

            self._status_item.setMenu_(menu)
        except Exception as e:
            logger.warning(f"Could not initialize NSStatusItem: {e}")

    def _setup_click_outside_monitor(self):
        """Monitors global mouse clicks to dismiss Omnibar when user clicks outside."""
        try:
            import Cocoa
            def _handler(event):
                if not getattr(self, "_is_visible", False):
                    return
                # 0.6s grace period after showing to prevent instant dismiss
                if time.time() - getattr(self, "_show_time", 0) < 0.6:
                    return
                loc = Cocoa.NSEvent.mouseLocation()
                if self._panel:
                    frame = self._panel.frame()
                    if not Cocoa.NSPointInRect(loc, frame):
                        self.hide()

            self._click_monitor = Cocoa.NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                Cocoa.NSEventMaskLeftMouseDown | Cocoa.NSEventMaskRightMouseDown,
                _handler
            )
        except Exception as e:
            logger.debug(f"Could not register click outside monitor: {e}")

    def resize_window(self, new_height: float):
        """Instantly updates the Cocoa NSPanel frame height without blocking animation stutter."""
        if not self._panel:
            return
        def _do():
            try:
                import Cocoa
                frame = self._panel.frame()
                if abs(frame.size.height - new_height) < 2:
                    return
                # Top edge invariance: maintain fixed top anchor so window expands downwards
                top_y = getattr(self, "_top_anchor", None)
                if top_y is None:
                    top_y = frame.origin.y + frame.size.height
                    self._top_anchor = top_y
                new_y = top_y - new_height
                new_frame = Cocoa.NSMakeRect(frame.origin.x, new_y, frame.size.width, new_height)
                if self._webview:
                    self._webview.setFrame_(Cocoa.NSMakeRect(0, 0, frame.size.width, new_height))
                self._panel.setFrame_display_animate_(new_frame, True, False)
            except Exception as e:
                logger.warning(f"Error resizing omnibar window: {e}")
        self.dispatch_main(_do)

    def show(self):
        """Displays and focuses the floating Omnibar, centered on the monitor where the cursor is."""
        def _do():
            if not self._panel:
                return
            self._show_time = time.time()
            try:
                import Cocoa
                # Save previous frontmost application so we can restore focus upon dismissal
                front_app = Cocoa.NSWorkspace.sharedWorkspace().frontmostApplication()
                if front_app and (not self._app or front_app.bundleIdentifier() != self._app.bundleIdentifier()):
                    self._prev_app = front_app

                mouse_loc = Cocoa.NSEvent.mouseLocation()
                target_screen = Cocoa.NSScreen.mainScreen()
                for s in Cocoa.NSScreen.screens():
                    if Cocoa.NSPointInRect(mouse_loc, s.frame()):
                        target_screen = s
                        break
                
                screen_frame = target_screen.frame()
                cur_frame = self._panel.frame()
                new_x = screen_frame.origin.x + (screen_frame.size.width - cur_frame.size.width) / 2
                top_y = screen_frame.origin.y + (screen_frame.size.height * 0.72)
                self._top_anchor = top_y
                new_y = top_y - cur_frame.size.height
                self._panel.setFrameOrigin_(Cocoa.NSMakePoint(new_x, new_y))
            except Exception as e:
                logger.debug(f"Could not recenter to mouse screen: {e}")

            if self._app:
                self._app.activateIgnoringOtherApps_(True)
            self._panel.makeKeyAndOrderFront_(None)
            self._panel.orderFrontRegardless()
            if self._webview:
                self._panel.makeFirstResponder_(self._webview)
            self._panel.setAlphaValue_(1.0)
            self._is_visible = True
            self.evaluate_js("if (window.resetOmnibar) { window.resetOmnibar(); } else { const inp = document.getElementById('query-input'); if (inp) { inp.focus(); inp.select(); } }")
        self.dispatch_main(_do)

    def hide(self):
        """Hides the Omnibar and restores focus to previous application."""
        def _do():
            if not getattr(self, "_is_visible", False):
                return
            self._is_visible = False
            if self._panel:
                self._panel.orderOut_(None)
            prev = getattr(self, "_prev_app", None)
            if prev:
                try:
                    import Cocoa
                    prev.activateWithOptions_(Cocoa.NSApplicationActivateIgnoringOtherApps)
                except Exception:
                    pass
                self._prev_app = None
        self.dispatch_main(_do)

    def toggle(self):
        """Toggles Omnibar visibility."""
        def _do():
            if self._is_visible:
                self.hide()
            else:
                self.show()
        self.dispatch_main(_do)

    def copy_text(self, text: str) -> bool:
        """Copies text to the macOS system clipboard."""
        try:
            import Cocoa
            pb = Cocoa.NSPasteboard.generalPasteboard()
            pb.clearContents()
            pb.setString_forType_(text, Cocoa.NSPasteboardTypeString)
            return True
        except Exception:
            try:
                import pyperclip
                pyperclip.copy(text)
                return True
            except Exception as e:
                logger.warning(f"Could not copy to clipboard: {e}")
                return False

    def on_model_status_requested(self):
        """Retrieves model status and updates the UI drawer."""
        if not self.brain:
            return
        status = self.brain.get_model_status()
        self.evaluate_js(f"window.displayModelDrawer({json.dumps(status)});")
        self.evaluate_js(f"window.updateModelStatus({json.dumps(status)});")

    def on_model_switch(self, model_name: str):
        """Dynamically switches active reasoning model."""
        if self.brain:
            self.brain.set_model(model_name)
            status = self.brain.get_model_status()
            self.evaluate_js(f"window.displayModelDrawer({json.dumps(status)});")
            self.evaluate_js(f"window.updateModelStatus({json.dumps(status)});")

    def on_query_submitted(self, query: str):
        """Processes submitted query with zero flicker and expands Result Drawer."""
        logger.info(f"Omnibar query submitted: '{query}'")
        
        def _execute():
            if not self.brain:
                return

            res = self.brain.execute_intent(query)
            # Dispatch result payload to webview
            self.evaluate_js(f"window.displayResult({json.dumps(res)});")

            # Speak response if audio active
            answer = res.get("response", "Task completed.")
            if self.audio and not res.get("silent", False):
                self.audio.speak(answer)

        threading.Thread(target=_execute, daemon=True).start()

    def on_voice_requested(self):
        """Called when user clicks mic button to speak."""
        logger.info("Voice capture initiated...")
        def _listen():
            if self.audio:
                text = self.audio.record_and_transcribe(duration=3.5)
                if text:
                    self.evaluate_js(f"document.getElementById('query-input').value = {json.dumps(text)};")
                    self.on_query_submitted(text)
                else:
                    self.audio.speak("I didn't catch that.")
        threading.Thread(target=_listen, daemon=True).start()

    def start_global_hotkey_listener(self):
        """Listens for Cmd+Shift+Space to summon/hide the Omnibar."""
        try:
            from pynput import keyboard
            current_keys = set()

            def on_press(key):
                current_keys.add(key)
                cmd_pressed = any(k in current_keys for k in [keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r])
                shift_pressed = any(k in current_keys for k in [keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r])
                space_pressed = (key == keyboard.Key.space)

                if cmd_pressed and shift_pressed and space_pressed:
                    self.toggle()

            def on_release(key):
                current_keys.discard(key)

            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.daemon = True
            listener.start()
            logger.info("Global hotkey (Cmd+Shift+Space) registered.")
        except Exception as e:
            logger.warning(f"Could not bind global hotkey: {e}")

    def check_or_start_instance(self) -> bool:
        """
        Ensures only a single instance of Aura runs.
        If another instance is active, sends 'show' command to bring it to front and returns False.
        """
        import socket
        import os

        socket_path = "/tmp/desktop_dom_aura.sock"

        # Attempt to communicate with already-running instance
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.6)
            s.connect(socket_path)
            s.sendall(b"show\n")
            s.close()
            logger.info("Aura already running; brought existing window to front.")
            return False
        except (socket.error, FileNotFoundError, ConnectionRefusedError):
            pass

        # Clean up stale socket file
        try:
            if os.path.exists(socket_path):
                os.remove(socket_path)
        except Exception:
            pass

        def _ipc_server():
            try:
                srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                srv.bind(socket_path)
                srv.listen(5)
                while True:
                    conn, _ = srv.accept()
                    data = conn.recv(1024)
                    if b"show" in data or b"toggle" in data:
                        self.show()
                    elif b"hide" in data:
                        self.hide()
                    conn.close()
            except Exception as e:
                logger.debug(f"IPC socket server terminated: {e}")

        t = threading.Thread(target=_ipc_server, daemon=True)
        t.start()
        return True

    def run(self):
        """Starts the native macOS Cocoa event loop."""
        if sys.platform == "darwin":
            if not self.check_or_start_instance():
                print("Aura is already running. Summoned existing window to front.")
                return
        self.setup_ui()
        self.start_global_hotkey_listener()
        self.show()
        if self._app:
            self._app.run()
