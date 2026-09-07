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
    width: 700px;
    border-radius: 16px;
    background: rgba(13, 15, 20, 0.94);
    backdrop-filter: blur(50px) saturate(190%);
    -webkit-backdrop-filter: blur(50px) saturate(190%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12), 0 24px 64px rgba(0, 0, 0, 0.75);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }
  .omnibar-card.listening {
    border-color: rgba(236, 72, 153, 0.6);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12), 0 24px 64px rgba(0, 0, 0, 0.75), 0 0 28px rgba(236, 72, 153, 0.2);
  }
  .omnibar-card.executing {
    border-color: rgba(14, 165, 233, 0.6);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12), 0 24px 64px rgba(0, 0, 0, 0.75), 0 0 28px rgba(14, 165, 233, 0.2);
  }
  .header-bar {
    height: 64px;
    display: flex;
    align-items: center;
    padding: 0 18px;
    gap: 14px;
    position: relative;
  }
  .brand-glyph {
    width: 30px;
    height: 30px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #0ea5e9;
    flex-shrink: 0;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .brand-glyph:hover {
    background: rgba(14, 165, 233, 0.15);
    border-color: rgba(14, 165, 233, 0.4);
    transform: scale(1.05);
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
    color: #f8fafc;
    font-size: 16px;
    font-weight: 450;
    letter-spacing: -0.2px;
    user-select: text !important;
    -webkit-user-select: text !important;
    cursor: text;
  }
  input#query-input::placeholder {
    color: rgba(255, 255, 255, 0.3);
    font-weight: 400;
  }
  #waveform-canvas {
    width: 68px;
    height: 24px;
    flex-shrink: 0;
  }
  .mic-btn {
    width: 30px;
    height: 30px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.09);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.18s ease;
    color: #94a3b8;
    flex-shrink: 0;
  }
  .mic-btn:hover {
    background: rgba(255, 255, 255, 0.09);
    color: #f8fafc;
  }
  .mic-btn.active {
    background: rgba(236, 72, 153, 0.2);
    border-color: rgba(236, 72, 153, 0.6);
    color: #f43f5e;
    animation: micPulse 1.4s infinite alternate ease-in-out;
  }
  @keyframes micPulse {
    0% { transform: scale(1); }
    100% { transform: scale(1.08); }
  }
  .status-badge {
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 9.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    background: rgba(255, 255, 255, 0.04);
    color: #94a3b8;
    border: 1px solid rgba(255, 255, 255, 0.08);
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .status-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #0ea5e9;
  }
  .progress-line {
    height: 1.5px;
    width: 100%;
    background: transparent;
    position: relative;
    overflow: hidden;
  }
  .progress-line.active {
    background: rgba(255, 255, 255, 0.04);
  }
  .progress-line.active::after {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    width: 35%;
    background: linear-gradient(90deg, transparent, #0ea5e9, transparent);
    animation: progressSlide 1.2s infinite cubic-bezier(0.4, 0, 0.2, 1);
  }
  @keyframes progressSlide {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(350%); }
  }
  .tray {
    display: flex;
    flex-direction: column;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(8, 9, 13, 0.35);
    padding: 6px 8px;
    gap: 2px;
    max-height: 240px;
    overflow-y: auto;
  }
  .suggestion-item {
    display: flex;
    align-items: center;
    padding: 7px 10px;
    border-radius: 8px;
    gap: 12px;
    cursor: pointer;
    transition: background 0.12s ease;
  }
  .suggestion-item:hover, .suggestion-item.selected {
    background: rgba(255, 255, 255, 0.06);
  }
  .suggestion-icon {
    width: 18px;
    height: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #94a3b8;
    flex-shrink: 0;
  }
  .suggestion-item.selected .suggestion-icon {
    color: #0ea5e9;
  }
  .suggestion-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
  }
  .suggestion-title {
    color: #f1f5f9;
    font-size: 13.5px;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .suggestion-subtitle {
    color: #64748b;
    font-size: 11px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .suggestion-badge {
    font-size: 9.5px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.04);
    color: #94a3b8;
    border: 1px solid rgba(255, 255, 255, 0.06);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .suggestion-item.selected .suggestion-badge {
    background: rgba(14, 165, 233, 0.12);
    color: #38bdf8;
    border-color: rgba(14, 165, 233, 0.25);
  }

  /* Minimalist Result Drawer */
  .result-drawer {
    display: none;
    flex-direction: column;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(7, 8, 12, 0.6);
    padding: 14px 18px;
    gap: 12px;
    max-height: 280px;
    overflow-y: auto;
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
    font-weight: 600;
    letter-spacing: 0.3px;
    text-transform: uppercase;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .pill-success {
    background: rgba(16, 185, 129, 0.12);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.25);
  }
  .pill-fast {
    background: rgba(14, 165, 233, 0.12);
    color: #38bdf8;
    border: 1px solid rgba(14, 165, 233, 0.25);
  }
  .pill-llm {
    background: rgba(168, 85, 247, 0.12);
    color: #c084fc;
    border: 1px solid rgba(168, 85, 247, 0.25);
  }
  .result-actions {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .action-btn {
    padding: 3px 9px;
    border-radius: 5px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .action-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
  }
  .action-btn.active {
    background: #0ea5e9;
    color: #0f172a;
    border-color: #0ea5e9;
    font-weight: 600;
  }
  .result-body {
    color: #e2e8f0;
    font-size: 13.5px;
    line-height: 1.55;
    white-space: pre-wrap;
    user-select: text;
    -webkit-user-select: text;
    word-break: break-word;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif;
  }

  /* Minimalist Model Drawer */
  .model-drawer {
    display: none;
    flex-direction: column;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(8, 9, 14, 0.85);
    padding: 12px 16px;
    gap: 6px;
    max-height: 250px;
    overflow-y: auto;
  }
  .model-drawer.visible {
    display: flex;
  }
  .model-drawer-title {
    font-size: 10px;
    font-weight: 650;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 2px 2px 6px 2px;
  }
  .model-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    border-radius: 7px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .model-card:hover {
    background: rgba(255, 255, 255, 0.07);
    border-color: rgba(255, 255, 255, 0.12);
  }
  .model-card.active {
    background: rgba(14, 165, 233, 0.08);
    border-color: rgba(14, 165, 233, 0.3);
  }
  .model-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .model-name {
    color: #f1f5f9;
    font-size: 13px;
    font-weight: 550;
  }
  .model-desc {
    color: #64748b;
    font-size: 10.5px;
  }
  .model-tag {
    font-size: 9.5px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.04);
    color: #94a3b8;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    letter-spacing: 0.3px;
  }
  .model-card.active .model-tag {
    background: #0ea5e9;
    color: #0c0e14;
    font-weight: 700;
  }

  .footer-bar {
    height: 32px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    background: rgba(6, 7, 10, 0.5);
    font-size: 10.5px;
    color: #64748b;
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
    background: rgba(255, 255, 255, 0.07);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 3px;
    padding: 0 3.5px;
    font-size: 8.5px;
    font-weight: 600;
    color: #94a3b8;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .local-tag {
    display: flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
    transition: background 0.12s ease;
    color: #94a3b8;
  }
  .local-tag:hover {
    background: rgba(255, 255, 255, 0.06);
    color: #f1f5f9;
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
    <div class="header-bar">
      <div class="brand-glyph" id="brand-orb" title="Aura AI — Click to switch models">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="12 2 2 7 12 12 22 7 12 2"/>
          <polyline points="2 17 12 22 22 17"/>
          <polyline points="2 12 12 17 22 12"/>
        </svg>
      </div>
      <div class="input-wrap">
        <input id="query-input" type="text" placeholder="Search commands, math, or ask Aura... (e.g. 'calculate 25 * 40')" autocomplete="off" autofocus />
      </div>
      <canvas id="waveform-canvas" width="136" height="48"></canvas>
      <div class="mic-btn" id="mic-btn" title="Toggle Voice Microphone">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          <line x1="12" y1="19" x2="12" y2="22"/>
        </svg>
      </div>
      <div class="status-badge" id="badge"><span class="status-dot" id="status-dot"></span><span id="badge-text">Ready</span></div>
    </div>

    <div class="progress-line" id="progress"></div>

    <div class="tray" id="tray">
      <!-- Dynamically generated suggestions -->
    </div>

    <div class="result-drawer" id="result-drawer">
      <div class="result-header">
        <div class="result-pills" id="result-pills">
          <span class="pill pill-success" id="result-status-pill">Success</span>
          <span class="pill pill-fast" id="result-engine-pill">Fast-Path</span>
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
        <span>Active Engine & Weights</span>
        <span id="model-conn-status">Checking...</span>
      </div>
      <div id="model-list" style="display: flex; flex-direction: column; gap: 4px;">
        <!-- Dynamically rendered models -->
      </div>
    </div>

    <div class="footer-bar">
      <div class="shortcuts">
        <span class="kbd-pill"><span class="kbd">↵</span> Run</span>
        <span class="kbd-pill"><span class="kbd">↑↓</span> Select</span>
        <span class="kbd-pill"><span class="kbd">Tab</span> Fill</span>
        <span class="kbd-pill"><span class="kbd">Esc</span> Dismiss</span>
      </div>
      <div class="local-tag" id="footer-model-tag" title="Click to view & switch local models">
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
    const resultDrawer = document.getElementById("result-drawer");
    const resultBody = document.getElementById("result-body");
    const resultStatusPill = document.getElementById("result-status-pill");
    const resultEnginePill = document.getElementById("result-engine-pill");
    const copyBtn = document.getElementById("copy-btn");
    const doneBtn = document.getElementById("done-btn");
    const modelDrawer = document.getElementById("model-drawer");
    const modelList = document.getElementById("model-list");
    const modelConnStatus = document.getElementById("model-conn-status");
    const footerModelTag = document.getElementById("footer-model-tag");
    const footerModelName = document.getElementById("footer-model-name");
    const modelDot = document.getElementById("model-dot");
    const brandOrb = document.getElementById("brand-orb");
    const canvas = document.getElementById("waveform-canvas");
    const ctx = canvas.getContext("2d");

    // Pure Vector SVG Icons (Zero Emojis)
    const ICONS = {
      search: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
      math: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/></svg>',
      media: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
      volume: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>',
      app: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
      screen: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
      model: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><circle cx="19" cy="6" r="2"/><circle cx="5" cy="6" r="2"/><circle cx="19" cy="18" r="2"/><circle cx="5" cy="18" r="2"/><line x1="12" y1="9" x2="12" y2="3"/><line x1="12" y1="15" x2="12" y2="21"/><line x1="9.5" y1="10.5" x2="6.5" y2="7.5"/><line x1="14.5" y1="10.5" x2="17.5" y2="7.5"/></svg>'
    };

    let isListening = false;
    let waveOffset = 0;
    let selectedIndex = 0;
    let currentSuggestions = [];
    let currentResultRaw = "";
    let autoCloseTimer = null;
    let isDrawerOpen = false;

    function drawWave() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const centerY = canvas.height / 2;
      const ampBase = isListening ? 10 : 3;
      const freq = isListening ? 0.08 : 0.04;

      ctx.beginPath();
      ctx.lineWidth = 1.4;
      ctx.strokeStyle = isListening ? "rgba(244, 63, 94, 0.85)" : "rgba(14, 165, 233, 0.75)";
      for (let x = 0; x < canvas.width; x++) {
        const envelope = Math.sin((x / canvas.width) * Math.PI);
        const y = centerY + Math.sin(x * freq + waveOffset) * ampBase * envelope;
        if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();

      waveOffset += isListening ? 0.18 : 0.04;
      requestAnimationFrame(drawWave);
    }
    drawWave();

    const defaultActions = [
      { iconType: "media", title: "Spotify Playback", subtitle: "Play Starboy on Spotify", query: "Play Starboy on Spotify", badge: "FAST-PATH" },
      { iconType: "math", title: "Calculator", subtitle: "Calculate 125 * 40 + 15", query: "Calculate 125 * 40 + 15", badge: "AST EVAL" },
      { iconType: "volume", title: "System Volume", subtitle: "Set volume to 80%", query: "Set volume to 80", badge: "HARDWARE" },
      { iconType: "app", title: "Launch Application", subtitle: "Open Calculator", query: "Open Calculator", badge: "APP" },
      { iconType: "screen", title: "Inspect Screen", subtitle: "What is on my screen?", query: "what is on my screen", badge: "DOM" },
      { iconType: "model", title: "Switch AI Models", subtitle: "View local Ollama weights", query: "/model", badge: "ENGINE" }
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
            title: "View & Switch Local Models",
            subtitle: "Manage Ollama connections & zero-model fast path",
            query: "/model",
            badge: "ENGINE"
          });
        }

        const mathClean = q.replace(/[^0-9+*/.() -]/g, "").trim();
        if (mathClean && /[+*/-]/.test(mathClean) && !mathClean.includes("**")) {
          try {
            const evaluated = Function('"use strict";return (' + mathClean + ')')();
            if (typeof evaluated === "number" && isFinite(evaluated)) {
              currentSuggestions.push({
                iconType: "math",
                title: `= ${evaluated}`,
                subtitle: `Calculate ${mathClean}`,
                query: q,
                badge: "MATH"
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
            badge: "SPOTIFY"
          });
        }

        if (q.toLowerCase().includes("volume") || q.toLowerCase().includes("mute")) {
          currentSuggestions.push({
            iconType: "volume",
            title: q,
            subtitle: "System Audio Hardware Bus (<30ms)",
            query: q,
            badge: "SYSTEM"
          });
        }

        if (q.toLowerCase().startsWith("open ") || q.toLowerCase().startsWith("launch ")) {
          const appName = q.replace(/^(open|launch)\s+/i, "").trim();
          currentSuggestions.push({
            iconType: "app",
            title: `Activate ${appName}`,
            subtitle: "DesktopApp Window Attachment (<80ms)",
            query: q,
            badge: "APP"
          });
        }

        if (q.toLowerCase().includes("screen") || q.toLowerCase().includes("window")) {
          currentSuggestions.push({
            iconType: "screen",
            title: "Inspect Active Screen & Elements",
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
          badge: "OLLAMA"
        });
      }

      renderSuggestions();
    }

    function renderSuggestions() {
      tray.innerHTML = "";
      tray.style.display = "flex";
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
            <div class="suggestion-title">${escapeHtml(item.title)}</div>
            <div class="suggestion-subtitle">${escapeHtml(item.subtitle)}</div>
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

    function notifyResize() {
      let contentHeight = 64 + 32 + 16;
      if (resultDrawer.classList.contains("visible")) {
        contentHeight = 64 + resultDrawer.scrollHeight + 32 + 18;
      } else if (modelDrawer.classList.contains("visible")) {
        contentHeight = 64 + modelDrawer.scrollHeight + 32 + 18;
      } else {
        contentHeight = 64 + (currentSuggestions.length * 44) + 32 + 14;
      }
      const targetHeight = Math.min(440, Math.max(80, contentHeight));
      window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
        action: "resize",
        height: targetHeight
      }));
    }

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
        if (isDrawerOpen) {
          closeDrawers();
        } else {
          window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "close" }));
        }
      }
    });

    micBtn.addEventListener("click", toggleMic);
    brandOrb.addEventListener("click", toggleModelDrawer);
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
        }, 1500);
      }
    });

    doneBtn.addEventListener("click", closeDrawers);

    function closeDrawers() {
      if (autoCloseTimer) clearTimeout(autoCloseTimer);
      resultDrawer.classList.remove("visible");
      modelDrawer.classList.remove("visible");
      tray.style.display = "flex";
      isDrawerOpen = false;
      badgeText.innerText = "Ready";
      statusDot.style.background = "#0ea5e9";
      card.classList.remove("executing");
      updateSuggestions();
    }

    function toggleMic() {
      isListening = !isListening;
      if (isListening) {
        micBtn.classList.add("active");
        card.classList.add("listening");
        badgeText.innerText = "Listening";
        statusDot.style.background = "#f43f5e";
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "start_listening" }));
      } else {
        micBtn.classList.remove("active");
        card.classList.remove("listening");
        badgeText.innerText = "Ready";
        statusDot.style.background = "#0ea5e9";
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "stop_listening" }));
      }
    }

    function submitQuery(query) {
      if (autoCloseTimer) clearTimeout(autoCloseTimer);
      card.classList.remove("listening");
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
      tray.style.display = "none";
      modelDrawer.classList.remove("visible");
      resultDrawer.classList.add("visible");
      isDrawerOpen = true;

      const respText = payload.response || "Completed successfully.";
      currentResultRaw = respText;
      resultBody.innerText = respText;

      const engine = payload.engine || "fast_path";
      const latency = payload.latency_ms ? `${payload.latency_ms}ms` : "";

      if (engine === "fast_path") {
        resultEnginePill.innerText = latency ? `Fast-Path · ${latency}` : "Fast-Path";
        resultEnginePill.className = "pill pill-fast";
      } else if (engine === "ollama") {
        resultEnginePill.innerText = latency ? `Ollama · ${latency}` : "Ollama";
        resultEnginePill.className = "pill pill-llm";
      } else {
        resultEnginePill.innerText = latency ? `Done · ${latency}` : "Done";
        resultEnginePill.className = "pill pill-fast";
      }

      badgeText.innerText = "Done";
      statusDot.style.background = "#10b981";

      notifyResize();

      const action = payload.action || "";
      if (["volume", "dark_mode", "clipboard_copy", "notes"].includes(action)) {
        autoCloseTimer = setTimeout(() => {
          window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "close" }));
        }, 2800);
      }
    };

    window.displayModelDrawer = function(status) {
      progress.classList.remove("active");
      tray.style.display = "none";
      resultDrawer.classList.remove("visible");
      modelDrawer.classList.add("visible");
      isDrawerOpen = true;

      const isConn = status.connected;
      const current = status.current_model || "Zero-Model Fast-Path";
      const models = status.available_models || [];

      modelConnStatus.innerHTML = isConn 
        ? `<span style="color:#10b981">Connected (${status.latency_ms}ms)</span>`
        : `<span style="color:#f59e0b">Offline (Fast-Path Mode)</span>`;

      modelList.innerHTML = "";

      const fpCard = document.createElement("div");
      fpCard.className = "model-card" + (current === "Zero-Model Fast-Path" ? " active" : "");
      fpCard.innerHTML = `
        <div class="model-info">
          <div class="model-name">Zero-Model Fast-Path</div>
          <div class="model-desc">Sub-25ms deterministic AST dispatch (0MB RAM overhead)</div>
        </div>
        <div class="model-tag">${current === "Zero-Model Fast-Path" ? "ACTIVE" : "SELECT"}</div>
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
          <div class="model-tag">${isAct ? "ACTIVE" : "SELECT"}</div>
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
      footerModelName.innerText = cur.length > 22 ? cur.slice(0, 20) + "…" : cur;
      if (status.connected) {
        modelDot.className = "dot-green";
      } else {
        modelDot.className = "dot-amber";
      }
    };

    updateSuggestions();
    input.focus();
    card.addEventListener("click", (e) => {
      if (!e.target.closest("#mic-btn") && !e.target.closest(".action-btn") && !e.target.closest("#footer-model-tag") && !e.target.closest(".model-card")) {
        input.focus();
      }
    });
    window.addEventListener("focus", () => {
      setTimeout(() => input.focus(), 50);
    });
    setTimeout(() => {
      input.focus();
      window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "get_model_status" }));
    }, 150);
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
    Native macOS floating glassmorphic spotlight bar powered by Cocoa & WebKit.
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
        self._panel.setHasShadow_(True)
        self._panel.setMovableByWindowBackground_(True)
        self._panel.setCollectionBehavior_(
            Cocoa.NSWindowCollectionBehaviorCanJoinAllSpaces |
            Cocoa.NSWindowCollectionBehaviorFullScreenAuxiliary
        )

        # Native Frosted Vibrancy View
        try:
            vibrancy = Cocoa.NSVisualEffectView.alloc().initWithFrame_(
                Cocoa.NSMakeRect(0, 0, bar_width, bar_height)
            )
            vibrancy.setMaterial_(Cocoa.NSVisualEffectMaterialHUDWindow)
            vibrancy.setBlendingMode_(Cocoa.NSVisualEffectBlendingModeBehindWindow)
            vibrancy.setState_(Cocoa.NSVisualEffectStateActive)
            vibrancy.setAutoresizingMask_(Cocoa.NSViewWidthSizable | Cocoa.NSViewHeightSizable)
            self._panel.contentView().addSubview_(vibrancy)
        except Exception as e:
            logger.debug(f"VisualEffectView not loaded: {e}")

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

    def resize_window(self, new_height: float):
        """Dynamically animates the Cocoa NSPanel frame height when suggestions expand."""
        if not self._panel:
            return
        def _do():
            try:
                import Cocoa
                frame = self._panel.frame()
                if abs(frame.size.height - new_height) < 4:
                    return
                delta = new_height - frame.size.height
                new_y = frame.origin.y - delta
                new_frame = Cocoa.NSMakeRect(frame.origin.x, new_y, frame.size.width, new_height)
                if self._webview:
                    self._webview.setFrame_(Cocoa.NSMakeRect(0, 0, frame.size.width, new_height))
                self._panel.setFrame_display_animate_(new_frame, True, True)
            except Exception as e:
                logger.warning(f"Error resizing omnibar window: {e}")
        self.dispatch_main(_do)

    def show(self):
        """Displays and focuses the floating Omnibar, centered on the monitor where the cursor is."""
        if self._panel:
            try:
                import Cocoa
                mouse_loc = Cocoa.NSEvent.mouseLocation()
                target_screen = Cocoa.NSScreen.mainScreen()
                for s in Cocoa.NSScreen.screens():
                    if Cocoa.NSPointInRect(mouse_loc, s.frame()):
                        target_screen = s
                        break
                
                screen_frame = target_screen.frame()
                cur_frame = self._panel.frame()
                new_x = screen_frame.origin.x + (screen_frame.size.width - cur_frame.size.width) / 2
                new_y = screen_frame.origin.y + (screen_frame.size.height * 0.58)
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
            self.evaluate_js("document.getElementById('query-input').focus();")

    def hide(self):
        """Hides the Omnibar."""
        if self._panel:
            self._panel.orderOut_(None)
            self._is_visible = False

    def toggle(self):
        """Toggles Omnibar visibility."""
        if self._is_visible:
            self.hide()
        else:
            self.show()

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

    def run(self):
        """Starts the native macOS Cocoa event loop."""
        self.setup_ui()
        self.start_global_hotkey_listener()
        self.show()
        if self._app:
            self._app.run()
