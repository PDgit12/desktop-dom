from __future__ import annotations
import sys
import json
import time
import logging
import threading
import webbrowser
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
  body.dragging, body.dragging * {
    cursor: -webkit-grabbing !important;
    cursor: grabbing !important;
    user-select: none !important;
  }
  .omnibar-card {
    width: 680px;
    border-radius: 14px;
    background: rgba(18, 20, 26, 0.94);
    backdrop-filter: blur(50px) saturate(210%);
    -webkit-backdrop-filter: blur(50px) saturate(210%);
    border: 1px solid rgba(255, 255, 255, 0.12);
    box-shadow: 0 32px 84px -10px rgba(0, 0, 0, 0.88), 0 0 0 1px rgba(255, 255, 255, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.15);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: border-color 0.15s ease, box-shadow 0.2s ease;
  }
  .omnibar-card.executing {
    border-color: rgba(56, 189, 248, 0.4);
    box-shadow: 0 32px 84px -10px rgba(0, 0, 0, 0.95), 0 0 20px -2px rgba(56, 189, 248, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.2);
  }
  .drag-handle-bar {
    width: 100%;
    height: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: -webkit-grab;
    cursor: grab;
    -webkit-app-region: drag;
    background: transparent;
    padding-top: 5px;
    transition: background 0.15s ease;
  }
  .drag-pill {
    width: 38px;
    height: 4px;
    border-radius: 2px;
    background: rgba(255, 255, 255, 0.22);
    transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .drag-handle-bar:hover .drag-pill {
    background: rgba(255, 255, 255, 0.55);
    width: 52px;
  }
  .header-bar {
    height: 52px;
    display: flex;
    align-items: center;
    padding: 0 16px;
    gap: 12px;
    position: relative;
    cursor: -webkit-grab;
    cursor: grab;
    -webkit-app-region: drag;
  }
  .search-icon {
    width: 18px;
    height: 18px;
    color: #94a3b8;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    -webkit-app-region: no-drag;
  }
  .input-wrap {
    flex: 1;
    display: flex;
    align-items: center;
    cursor: text;
    -webkit-app-region: no-drag;
  }
  input#query-input {
    width: 100%;
    background: transparent;
    border: none;
    outline: none;
    color: #f8fafc;
    font-size: 15.5px;
    font-weight: 450;
    letter-spacing: -0.2px;
    user-select: text !important;
    -webkit-user-select: text !important;
    cursor: text;
  }
  input#query-input::placeholder {
    color: #64748b;
    font-weight: 400;
  }
  .header-tools {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
    -webkit-app-region: no-drag;
  }
  .workspace-pill-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.10);
    font-size: 11px;
    font-weight: 500;
    color: #cbd5e1;
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .workspace-pill-btn:hover {
    background: rgba(255, 255, 255, 0.09);
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.18);
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
  .mic-btn, .settings-btn {
    width: 28px;
    height: 28px;
    border-radius: 7px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.12s ease;
    color: #94a3b8;
  }
  .mic-btn:hover, .settings-btn:hover {
    background: rgba(255, 255, 255, 0.09);
    color: #f8fafc;
    border-color: rgba(255, 255, 255, 0.14);
  }
  .mic-btn.active {
    background: rgba(239, 68, 68, 0.15);
    border-color: rgba(239, 68, 68, 0.4);
    color: #ef4444;
  }
  .status-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 3px 8px;
    border-radius: 5px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.06);
    font-size: 10.5px;
    font-weight: 500;
    color: #94a3b8;
    letter-spacing: 0.1px;
  }
  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.4);
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
    max-height: 340px;
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

  /* 1-Click Misfire Feedback Chip & Inline Teach Form */
  .misfire-feedback-bar {
    display: none;
    flex-direction: column;
    gap: 8px;
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    transition: all 0.2s ease;
  }
  .misfire-feedback-bar.visible {
    display: flex;
  }
  .misfire-chip {
    align-self: flex-start;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 8px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    font-size: 11px;
    font-weight: 500;
    color: #71717a;
    cursor: pointer;
    transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1);
    user-select: none;
  }
  .misfire-chip:hover {
    background: rgba(56, 189, 248, 0.08);
    border-color: rgba(56, 189, 248, 0.3);
    color: #38bdf8;
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(56, 189, 248, 0.12);
  }
  .misfire-chip svg {
    color: inherit;
    flex-shrink: 0;
  }
  .misfire-inline-form {
    display: flex;
    flex-direction: column;
    gap: 6px;
    background: rgba(0, 0, 0, 0.25);
    border: 1px solid rgba(56, 189, 248, 0.2);
    border-radius: 8px;
    padding: 8px 10px;
    animation: misfireFadeIn 0.18s cubic-bezier(0.16, 1, 0.3, 1);
  }
  @keyframes misfireFadeIn {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .misfire-label {
    font-size: 10px;
    font-weight: 500;
    color: #94a3b8;
    letter-spacing: 0.2px;
  }
  .misfire-input-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .misfire-input {
    flex: 1;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 5px;
    padding: 5px 8px;
    font-size: 11.5px;
    color: #f4f4f5;
    outline: none;
    transition: all 0.12s ease;
  }
  .misfire-input:focus {
    border-color: #38bdf8;
    box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.15);
    background: rgba(56, 189, 248, 0.05);
  }
  .misfire-submit-btn {
    background: #0284c7;
    color: #ffffff;
    border: none;
    border-radius: 5px;
    padding: 5px 10px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.12s ease;
    white-space: nowrap;
  }
  .misfire-submit-btn:hover {
    background: #0369a1;
  }
  .misfire-submit-btn:active {
    transform: scale(0.97);
  }
  .misfire-cancel-btn {
    background: transparent;
    border: none;
    color: #71717a;
    font-size: 12px;
    cursor: pointer;
    padding: 4px 6px;
    border-radius: 4px;
    transition: all 0.1s ease;
  }
  .misfire-cancel-btn:hover {
    color: #f4f4f5;
    background: rgba(255, 255, 255, 0.08);
  }
  .misfire-feedback-msg {
    font-size: 11px;
    font-weight: 500;
    color: #34d399;
    display: flex;
    align-items: center;
    gap: 4px;
    animation: misfireFadeIn 0.15s ease;
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

  /* Project / Workspace Switcher Drawer */
  .project-drawer {
    display: none;
    flex-direction: column;
    padding: 10px 14px;
    gap: 4px;
    max-height: 240px;
    overflow-y: auto;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
  }
  .project-drawer.visible {
    display: flex !important;
  }
  .project-card {
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
  .project-card:hover {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.08);
  }
  .project-card.active {
    background: rgba(56, 189, 248, 0.1);
    border-color: rgba(56, 189, 248, 0.25);
  }

  /* Interactive Onboarding Drawer */
  .onboarding-drawer {
    display: none;
    flex-direction: column;
    padding: 12px 16px;
    gap: 10px;
    max-height: 320px;
    overflow-y: auto;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    opacity: 0;
    transform: translateY(-4px);
    transition: opacity 0.16s ease, transform 0.16s ease;
  }
  .onboarding-drawer::-webkit-scrollbar {
    width: 4px;
  }
  .onboarding-drawer::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 4px;
  }
  .onboarding-drawer.visible {
    display: flex !important;
    opacity: 1;
    transform: translateY(0);
  }
  .onb-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .onb-title {
    font-size: 11px;
    font-weight: 600;
    color: #38bdf8;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .onb-close-btn {
    background: transparent;
    border: none;
    color: #71717a;
    font-size: 16px;
    line-height: 1;
    cursor: pointer;
    padding: 2px 5px;
    border-radius: 4px;
    transition: all 0.1s ease;
  }
  .onb-close-btn:hover {
    color: #f4f4f5;
    background: rgba(255, 255, 255, 0.08);
  }
  .onb-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .onb-field {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .onb-label {
    font-size: 10px;
    color: #71717a;
    font-weight: 500;
  }
  .onb-input {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 6px 9px;
    font-size: 11.5px;
    color: #f4f4f5;
    outline: none;
    transition: all 0.12s ease;
  }
  .onb-input:focus {
    border-color: #38bdf8;
    box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.18);
    background: rgba(56, 189, 248, 0.06);
  }
  .onb-apps-label {
    font-size: 10px;
    color: #71717a;
    font-weight: 500;
    margin-top: 2px;
  }
  .onb-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }
  .onb-chip {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    border-radius: 5px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    font-size: 10.5px;
    color: #a1a1aa;
    cursor: pointer;
    user-select: none;
    transition: all 0.12s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .onb-chip:hover {
    border-color: rgba(56, 189, 248, 0.4);
    background: rgba(255, 255, 255, 0.08);
    color: #f4f4f5;
  }
  .onb-chip.active {
    background: rgba(56, 189, 248, 0.12);
    border-color: rgba(56, 189, 248, 0.3);
    color: #38bdf8;
  }
  .onb-isolation-banner {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 8px;
    background: rgba(16, 185, 129, 0.08);
    border: 1px solid rgba(16, 185, 129, 0.2);
    border-radius: 6px;
    font-size: 10px;
    color: #34d399;
  }
  .onb-btn-bar {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 4px;
  }
  .onb-confirm-btn {
    background: #0284c7;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .onb-confirm-btn:hover {
    background: #0369a1;
  }
  .onb-confirm-btn:active {
    transform: scale(0.98);
  }
  .onb-cancel-btn {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #a1a1aa;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 11px;
    cursor: pointer;
    transition: all 0.12s ease;
  }
  .onb-cancel-btn:hover {
    color: #f4f4f5;
    background: rgba(255, 255, 255, 0.08);
  }
  .onb-cancel-btn:active {
    transform: scale(0.98);
  }

  /* Interactive Settings Drawer */
  .settings-drawer {
    display: none;
    flex-direction: column;
    padding: 12px 16px;
    gap: 10px;
    max-height: 330px;
    overflow-y: auto;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    opacity: 0;
    transform: translateY(-4px);
    transition: opacity 0.16s ease, transform 0.16s ease;
  }
  .settings-drawer::-webkit-scrollbar {
    width: 4px;
  }
  .settings-drawer::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 4px;
  }
  .settings-drawer.visible {
    display: flex !important;
    opacity: 1;
    transform: translateY(0);
  }
  .settings-collabs-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 110px;
    overflow-y: auto;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    padding: 6px 8px;
  }
  .settings-collab-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 3px 6px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.03);
    font-size: 11px;
    color: #e4e4e7;
  }
  .settings-collab-info {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .settings-del-btn {
    background: transparent;
    border: none;
    color: #ef4444;
    cursor: pointer;
    font-size: 12px;
    line-height: 1;
    padding: 2px 5px;
    border-radius: 3px;
    transition: background 0.1s ease;
  }
  .settings-del-btn:hover {
    background: rgba(239, 68, 68, 0.15);
  }
  .settings-add-row {
    display: flex;
    gap: 6px;
    align-items: center;
    margin-top: 4px;
  }
  .settings-add-btn {
    background: rgba(167, 139, 250, 0.15);
    border: 1px solid rgba(167, 139, 250, 0.3);
    color: #a78bfa;
    border-radius: 5px;
    padding: 5px 10px;
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.12s ease;
  }
  .settings-add-btn:hover {
    background: rgba(167, 139, 250, 0.25);
  }

  /* Composio Cloud Integration Cards */
  .composio-connect-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
    margin-top: 2px;
  }
  .composio-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 7px 10px;
    border-radius: 7px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.07);
    transition: all 0.12s ease;
  }
  .composio-card:hover {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(255, 255, 255, 0.12);
  }
  .composio-card.connected {
    background: rgba(16, 185, 129, 0.06);
    border-color: rgba(16, 185, 129, 0.22);
  }
  .composio-card.pending {
    background: rgba(234, 179, 8, 0.06);
    border-color: rgba(234, 179, 8, 0.22);
  }
  .composio-info {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .composio-icon {
    font-size: 14px;
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.06);
    flex-shrink: 0;
  }
  .composio-details {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .composio-name {
    font-size: 11px;
    font-weight: 550;
    color: #f1f5f9;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .composio-sub {
    font-size: 9.5px;
    color: #64748b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .composio-actions {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }
  .composio-btn {
    font-size: 10px;
    font-weight: 500;
    padding: 3px 8px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.1s ease;
    border: none;
  }
  .composio-btn-connect {
    background: rgba(56, 189, 248, 0.12);
    color: #38bdf8;
    border: 1px solid rgba(56, 189, 248, 0.25);
  }
  .composio-btn-connect:hover {
    background: rgba(56, 189, 248, 0.22);
    border-color: rgba(56, 189, 248, 0.45);
  }
  .composio-btn-disconnect {
    background: rgba(239, 68, 68, 0.08);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.18);
  }
  .composio-btn-disconnect:hover {
    background: rgba(239, 68, 68, 0.18);
    border-color: rgba(239, 68, 68, 0.35);
  }
  .composio-btn-sync {
    background: rgba(255, 255, 255, 0.05);
    color: #cbd5e1;
    border: 1px solid rgba(255, 255, 255, 0.1);
  }
  .composio-btn-sync:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
  }

  .settings-btn {
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
  .settings-btn:hover {
    background: rgba(255, 255, 255, 0.08);
    color: #f4f4f5;
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
    <div class="drag-handle-bar" id="drag-handle-bar" title="Drag anywhere to reposition">
      <div class="drag-pill"></div>
    </div>
    <div class="header-bar" id="header-bar">
      <div class="search-icon">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/>
          <line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      </div>
      <div class="input-wrap">
        <input id="query-input" type="text" placeholder="Search commands, meetings, contacts, or type an action..." autocomplete="off" spellcheck="false" autofocus />
      </div>
      <div class="header-tools">
        <div class="workspace-pill-btn" id="workspace-pill" title="Active Sovereign Workspace (Click for Settings)">
          <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #38bdf8; box-shadow: 0 0 6px rgba(56, 189, 248, 0.6);"></span>
          <span id="workspace-name">Workspace</span>
        </div>
        <div class="model-pill-btn" id="model-pill" title="Intent Routing Engine" style="display: none;">
          <span id="header-model-name">Native</span>
          <span class="chevron">▾</span>
        </div>
        <div class="mic-btn" id="mic-btn" title="Toggle Voice Dictation">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
            <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="22"/>
          </svg>
        </div>
        <div class="settings-btn" id="settings-btn" title="Knowledge Graph & Collaborator Settings">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </div>
        <div class="status-badge" id="badge" title="Native Accessibility & Intent Kernel Active">
          <span class="status-dot" id="status-dot"></span>
          <span id="badge-text">Connected</span>
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
      <div class="misfire-feedback-bar" id="misfire-feedback-bar" style="display: none;">
        <div class="misfire-chip" id="misfire-chip" title="Wrong tool? Teach Aura your preference">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
          <span>Wrong tool? Teach Aura</span>
        </div>
        <div class="misfire-inline-form" id="misfire-inline-form" style="display: none;">
          <span class="misfire-label" id="misfire-label">What tool should have opened?</span>
          <div class="misfire-input-row">
            <input type="text" class="misfire-input" id="misfire-tool-input" placeholder="e.g. Zoom, Linear, Notes..." autocomplete="off" spellcheck="false" />
            <button class="misfire-submit-btn" id="misfire-submit-btn">Teach Aura</button>
            <button class="misfire-cancel-btn" id="misfire-cancel-btn" title="Cancel">✕</button>
          </div>
        </div>
        <div class="misfire-feedback-msg" id="misfire-feedback-msg" style="display: none;">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
          <span id="misfire-feedback-text">Preference updated — Aura learned!</span>
        </div>
      </div>
    </div>

    <div class="model-drawer" id="model-drawer" style="display: none;">
      <div class="model-drawer-title">
        <span>Active Engine & Local Models</span>
        <span id="model-conn-status">Checking...</span>
      </div>
      <div id="model-list" style="display: flex; flex-direction: column; gap: 2px;">
        <!-- Dynamically rendered models -->
      </div>
    </div>

    <div class="project-drawer" id="project-drawer" style="display: none;">
      <div class="model-drawer-title">
        <span>Active Sovereign Workspace</span>
        <span style="font-size: 9px; color: #38bdf8;">Cmd+P to Switch</span>
      </div>
      <div id="project-list" style="display: flex; flex-direction: column; gap: 4px;">
        <!-- Dynamically rendered projects -->
      </div>
      <div class="settings-add-row" style="margin-top: 6px;">
        <input type="text" class="onb-input" id="project-new-name" placeholder="Enter new project or workspace name..." style="flex: 1;" />
        <button class="settings-add-btn" id="project-add-btn" style="background: #0284c7; min-width: 70px;" type="button">+ Switch</button>
      </div>
    </div>

    <div class="onboarding-drawer" id="onboarding-drawer" style="display: none;">
      <div class="onb-header">
        <div class="onb-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
          <span>Personal Command Layer · Quick Setup</span>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <div class="status-badge" style="background: rgba(56, 189, 248, 0.1); color: #38bdf8;" id="onb-status-badge">1-Click Connect</div>
          <button class="onb-close-btn" id="onb-close-btn" title="Dismiss (Esc)">×</button>
        </div>
      </div>

      <div style="font-size: 11.5px; color: #a1a1aa; line-height: 1.4;">
        Connect your work tools via Composio. Aura automatically maps your calendar, repositories, and team members into your local Knowledge Graph with zero manual typing.
      </div>

      <div class="onb-field" style="margin-top: 2px;">
        <div class="composio-connect-grid" id="onb-composio-grid">
          <!-- Dynamically populated Composio integration cards -->
        </div>
      </div>

      <div id="onb-discovery-banner" style="display: none; padding: 8px 12px; background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 6px; font-size: 11px; color: #34d399;">
        <div style="display: flex; align-items: center; gap: 6px; font-weight: 600;">
          <span>✓</span> <span id="onb-discovery-title">Connected to Cloud Data Layer</span>
        </div>
        <div id="onb-discovery-details" style="margin-top: 3px; font-size: 10px; color: #a7f3d0; opacity: 0.9;">
          Auto-discovering meetings, team contacts, and active repositories...
        </div>
      </div>

      <details id="onb-manual-accordion" style="margin-top: 2px; border: 1px solid rgba(255, 255, 255, 0.07); border-radius: 6px; padding: 6px 10px; font-size: 11px; color: #71717a;">
        <summary style="cursor: pointer; user-select: none; color: #a1a1aa; font-weight: 500;">
          <span>Customize or Override Details (Optional)</span>
        </summary>
        <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 8px;">
          <div class="onb-grid">
            <div class="onb-field">
              <label class="onb-label">Full Name</label>
              <input type="text" class="onb-input" id="onb-name" value="" placeholder="Your full name" />
            </div>
            <div class="onb-field">
              <label class="onb-label">Role / Professional Title</label>
              <input type="text" class="onb-input" id="onb-role" value="" placeholder="Your role or title" />
            </div>
            <div class="onb-field">
              <label class="onb-label">Primary Organization / Team</label>
              <input type="text" class="onb-input" id="onb-company" value="" placeholder="Your company or team" />
            </div>
            <div class="onb-field">
              <label class="onb-label">Habitual Focus Playlist</label>
              <input type="text" class="onb-input" id="onb-playlist" value="" placeholder="e.g. Deep Focus, Lo-Fi Beats" />
            </div>
          </div>
          <div class="onb-field">
            <label class="onb-label">Collaborators (Locked in Knowledge Graph)</label>
            <input type="text" class="onb-input" id="onb-collabs" value="" placeholder="Name (email), Name (email)" />
          </div>
          <div class="onb-field">
            <label class="onb-apps-label">Detected Machine Applications (Bound to Level 2 Fast-Paths)</label>
            <div class="onb-chips" id="onb-apps-chips">
              <!-- Dynamically populated chips -->
            </div>
            <div class="settings-add-row" style="margin-top: 6px;">
              <input type="text" class="onb-input" id="onb-new-app-name" placeholder="App Name (e.g. Granola, Figma, Linear, Notion)" style="flex: 3;" />
              <input type="text" class="onb-input" id="onb-new-app-cat" placeholder="Capability / Intent (e.g. meeting, design, tasks)" style="flex: 2;" />
              <button class="settings-add-btn" id="onb-add-app-btn" type="button">+ Add App</button>
            </div>
          </div>
        </div>
      </details>

      <div class="onb-btn-bar" style="margin-top: 6px;">
        <button class="onb-cancel-btn" id="onb-cancel-btn">Skip for now</button>
        <button class="onb-confirm-btn" id="onb-confirm-btn" style="background: linear-gradient(135deg, #0284c7, #2563eb); font-weight: 600;">Launch Aura ➔</button>
      </div>
    </div>

    <div class="settings-drawer" id="settings-drawer" style="display: none;">
      <div class="onb-header">
        <div class="onb-title" style="color: #a78bfa;">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          <span>Memory & Intent Settings</span>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <div class="status-badge" style="background: rgba(167, 139, 250, 0.1); color: #a78bfa;" id="settings-status-badge">Live Config</div>
          <button class="onb-close-btn" id="settings-close-btn" title="Dismiss (Esc)">×</button>
        </div>
      </div>
      <div class="onb-grid">
        <div class="onb-field">
          <label class="onb-label">Full Name</label>
          <input type="text" class="onb-input" id="settings-name" />
        </div>
        <div class="onb-field">
          <label class="onb-label">Role</label>
          <input type="text" class="onb-input" id="settings-role" />
        </div>
        <div class="onb-field">
          <label class="onb-label">Company</label>
          <input type="text" class="onb-input" id="settings-company" />
        </div>
        <div class="onb-field">
          <label class="onb-label">Focus Playlist</label>
          <input type="text" class="onb-input" id="settings-playlist" />
        </div>
      </div>
      <div class="onb-field">
        <label class="onb-label">Connected Applications (Knowledge Graph Apps Cluster)</label>
        <div class="settings-collabs-list" id="settings-apps-container">
          <!-- Populated with connected app rows -->
        </div>
        <div class="settings-add-row">
          <input type="text" class="onb-input" id="settings-new-app-name" placeholder="App Name (e.g. Granola, Figma, Linear)" style="flex: 3;" />
          <input type="text" class="onb-input" id="settings-new-app-cat" placeholder="Capability / Intent (e.g. meeting, design, tasks)" style="flex: 2;" />
          <button class="settings-add-btn" id="settings-add-app-btn" type="button">+ Add App</button>
        </div>
      </div>
      <div class="onb-field">
        <label class="onb-label">Team Collaborators (Knowledge Graph)</label>
        <div class="settings-collabs-list" id="settings-collabs-container">
          <!-- Populated with collaborator rows -->
        </div>
        <div class="settings-add-row">
          <input type="text" class="onb-input" id="settings-new-name" placeholder="Teammate Name" style="flex: 2;" />
          <input type="text" class="onb-input" id="settings-new-email" placeholder="Email" style="flex: 2;" />
          <input type="text" class="onb-input" id="settings-new-role" placeholder="Role (e.g. CTO)" style="flex: 1.5;" />
          <button class="settings-add-btn" id="settings-add-collab-btn">+ Add</button>
        </div>
      </div>
      <div class="onb-field" style="margin-top: 4px;">
        <label class="onb-label" style="display: flex; justify-content: space-between; align-items: center;">
          <span>Composio API Key</span>
          <span id="composio-key-badge" style="font-size: 9px; color: #a1a1aa; text-transform: uppercase;">Checking...</span>
        </label>
        <div class="settings-add-row">
          <input type="password" class="onb-input" id="settings-composio-key" placeholder="Enter COMPOSIO_API_KEY (comp_...)" style="flex: 1;" />
          <button class="settings-add-btn" id="settings-save-key-btn" style="background: #059669; min-width: 90px;" type="button">Save Key</button>
        </div>
      </div>
      <div class="onb-field" style="margin-top: 4px;">
        <label class="onb-label" style="display: flex; justify-content: space-between; align-items: center;">
          <span>Cloud Integrations (Composio Sovereignty Layer)</span>
          <span style="font-size: 9px; color: #a78bfa; text-transform: uppercase; letter-spacing: 0.05em;">Isolated Work Cluster</span>
        </label>
        <div class="composio-connect-grid" id="settings-composio-grid">
          <!-- Dynamically populated Composio integration cards -->
        </div>
      </div>
      <div class="onb-btn-bar">
        <button class="onb-cancel-btn" id="settings-reset-btn" title="Re-run onboarding flow">Re-run Onboarding</button>
        <button class="onb-confirm-btn" id="settings-save-btn" style="background: #7c3aed;">Save Changes</button>
      </div>
    </div>

    <div class="footer-bar">
      <div class="shortcuts">
        <span class="kbd-pill"><span class="kbd">↵</span> Run</span>
        <span class="kbd-pill"><span class="kbd">↑↓</span> Navigate</span>
        <span class="kbd-pill"><span class="kbd">Tab</span> Fill</span>
        <span class="kbd-pill"><span class="kbd">Esc</span> Dismiss</span>
        <span class="kbd-pill drag-hint" style="cursor: -webkit-grab; cursor: grab;" title="Click and drag anywhere to move"><span class="kbd">✥</span> Drag Anywhere</span>
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <div class="local-tag" id="footer-onb-tag" style="cursor: pointer;" title="Open Onboarding & Brain Topology">
          <div class="dot-green" id="onb-footer-dot"></div>
          <span id="footer-onb-text">Kernel: Online</span>
        </div>
        <div class="local-tag" id="footer-model-tag" style="display: none;">
          <div class="dot-green" id="model-dot"></div>
          <span id="footer-model-name">Native</span>
        </div>
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
    const onboardingDrawer = document.getElementById("onboarding-drawer");
    const onbName = document.getElementById("onb-name");
    const onbRole = document.getElementById("onb-role");
    const onbCompany = document.getElementById("onb-company");
    const onbPlaylist = document.getElementById("onb-playlist");
    const onbCollabs = document.getElementById("onb-collabs");
    const onbAppsChips = document.getElementById("onb-apps-chips");
    const onbNewAppName = document.getElementById("onb-new-app-name");
    const onbNewAppCat = document.getElementById("onb-new-app-cat");
    const onbAddAppBtn = document.getElementById("onb-add-app-btn");
    const onbConfirmBtn = document.getElementById("onb-confirm-btn");
    const onbCancelBtn = document.getElementById("onb-cancel-btn");
    const footerOnbTag = document.getElementById("footer-onb-tag");
    const onbStatusBadge = document.getElementById("onb-status-badge");
    const settingsBtn = document.getElementById("settings-btn");
    const settingsDrawer = document.getElementById("settings-drawer");
    const settingsName = document.getElementById("settings-name");
    const settingsRole = document.getElementById("settings-role");
    const settingsCompany = document.getElementById("settings-company");
    const settingsPlaylist = document.getElementById("settings-playlist");
    const settingsAppsContainer = document.getElementById("settings-apps-container");
    const settingsNewAppName = document.getElementById("settings-new-app-name");
    const settingsNewAppCat = document.getElementById("settings-new-app-cat");
    const settingsAddAppBtn = document.getElementById("settings-add-app-btn");
    const settingsCollabsContainer = document.getElementById("settings-collabs-container");
    const settingsNewName = document.getElementById("settings-new-name");
    const settingsNewEmail = document.getElementById("settings-new-email");
    const settingsNewRole = document.getElementById("settings-new-role");
    const settingsAddCollabBtn = document.getElementById("settings-add-collab-btn");
    const settingsCloseBtn = document.getElementById("settings-close-btn");
    const settingsResetBtn = document.getElementById("settings-reset-btn");
    const settingsSaveBtn = document.getElementById("settings-save-btn");
    const settingsStatusBadge = document.getElementById("settings-status-badge");
    const misfireFeedbackBar = document.getElementById("misfire-feedback-bar");
    const misfireChip = document.getElementById("misfire-chip");
    const misfireInlineForm = document.getElementById("misfire-inline-form");
    const misfireToolInput = document.getElementById("misfire-tool-input");
    const misfireSubmitBtn = document.getElementById("misfire-submit-btn");
    const misfireCancelBtn = document.getElementById("misfire-cancel-btn");
    const misfireFeedbackMsg = document.getElementById("misfire-feedback-msg");
    const misfireFeedbackText = document.getElementById("misfire-feedback-text");
    const misfireLabel = document.getElementById("misfire-label");

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
    let currentMisfireQuery = "";
    let currentMisfireWrongApp = "";
    let lastSubmittedQuery = "";

    const defaultActions = [
      { iconType: "app", title: "Top Apps & Brain Onboarding", subtitle: "Discovered apps & knowledge graph topology", query: "/onboard", badge: "Brain" },
      { iconType: "app", title: "I Have a Meeting", subtitle: "Launch bound meeting companion (Level 2.5 Ghost)", query: "i have a meeting", badge: "Intent" },
      { iconType: "app", title: "Memory & Collaborators", subtitle: "Manage profile, collaborators & app bindings", query: "/settings", badge: "Config" },
      { iconType: "app", title: "Message a Colleague", subtitle: "Draft a message to a contact", query: "message ", badge: "Intent" },
      { iconType: "app", title: "Check My Calendar", subtitle: "View today's schedule and upcoming events", query: "what is on my calendar", badge: "Context" },
      { iconType: "screen", title: "What was I doing?", subtitle: "Summarize active desktop context & focus", query: "what was I doing?", badge: "Context" },
      { iconType: "app", title: "Open My Repo", subtitle: "Active GitHub workspace & pull requests", query: "open my repo", badge: "Dev" },
      { iconType: "media", title: "Play Focus Playlist", subtitle: "Play verified focus soundtrack on Spotify", query: "play playlist", badge: "Music" },
      { iconType: "math", title: "Quick Calculation", subtitle: "Evaluate arithmetic expression", query: "125 * 40 + 15", badge: "Math" }
    ];

    function updateSuggestions() {
      if (isDrawerOpen) return;
      const q = input.value.trim();
      currentSuggestions = [];

      if (!q) {
        currentSuggestions = defaultActions;
      } else {
        if (q.toLowerCase().includes("meet") || q.toLowerCase().includes("granola") || q.toLowerCase().includes("call") || q.toLowerCase().includes("sync")) {
          currentSuggestions.push({
            iconType: "app",
            title: "Meeting Companion Intent",
            subtitle: "Launch bound meeting workspace & notes",
            query: q,
            badge: "Meeting"
          });
        }

        if (q.toLowerCase().includes("onboard") || q.toLowerCase().includes("top app") || q.toLowerCase().includes("most used") || q.toLowerCase().includes("graph")) {
          currentSuggestions.push({
            iconType: "app",
            title: "Top Apps & Brain Topology",
            subtitle: "Inspect discovered apps and semantic graph",
            query: "/onboard",
            badge: "Brain"
          });
        }

        if (q.startsWith("/model") || q === "models" || q === "status") {
          currentSuggestions.push({
            iconType: "model",
            title: "Active Intelligence Engine",
            subtitle: "Local neural weights & fast-path intent router",
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
            subtitle: "Play in Spotify",
            query: q,
            badge: "Music"
          });
        }

        if (q.toLowerCase().includes("volume") || q.toLowerCase().includes("mute")) {
          currentSuggestions.push({
            iconType: "volume",
            title: q,
            subtitle: "System audio control",
            query: q,
            badge: "System"
          });
        }

        if (q.toLowerCase().startsWith("open ") || q.toLowerCase().startsWith("launch ")) {
          const appName = q.replace(/^(open|launch)\s+/i, "").trim();
          currentSuggestions.push({
            iconType: "app",
            title: `Open ${appName}`,
            subtitle: "Launch or focus application",
            query: q,
            badge: "App"
          });
        }

        if (q.toLowerCase().includes("screen") || q.toLowerCase().includes("window")) {
          currentSuggestions.push({
            iconType: "screen",
            title: "Inspect Active Screen",
            subtitle: "Extract semantic UI hierarchy",
            query: q,
            badge: "Screen"
          });
        }

        if (q.startsWith("/settings") || q.toLowerCase().includes("setting") || q === "config" || q === "preferences") {
          currentSuggestions.push({
            iconType: "app",
            title: "Memory & Collaborator Settings",
            subtitle: "Manage profile, collaborators & app bindings",
            query: "/settings",
            badge: "Config"
          });
        }

        currentSuggestions.push({
          iconType: "search",
          title: q,
          subtitle: "Execute intent via local intelligence",
          query: q,
          badge: "Intent"
        });
      }

      renderSuggestions();
    }

    function renderSuggestions() {
      tray.innerHTML = "";
      commandSection.style.display = "block";
      resultDrawer.classList.remove("visible");
      modelDrawer.classList.remove("visible");
      onboardingDrawer.classList.remove("visible");
      if (settingsDrawer) {
        settingsDrawer.classList.remove("visible");
        settingsDrawer.style.display = "none";
      }
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
      } else if (onboardingDrawer.classList.contains("visible")) {
        contentHeight = 52 + onboardingDrawer.scrollHeight + 32 + 16;
      } else if (settingsDrawer && settingsDrawer.classList.contains("visible")) {
        contentHeight = 52 + settingsDrawer.scrollHeight + 32 + 16;
      } else {
        contentHeight = 52 + 24 + (currentSuggestions.length * 38) + 32 + 12;
      }
      const targetHeight = Math.min(520, Math.max(80, contentHeight));
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
      modelDrawer.style.display = "none";
      onboardingDrawer.classList.remove("visible");
      onboardingDrawer.style.display = "none";
      if (settingsDrawer) {
        settingsDrawer.classList.remove("visible");
        settingsDrawer.style.display = "none";
      }
      if (misfireFeedbackBar) {
        misfireFeedbackBar.classList.remove("visible");
        misfireFeedbackBar.style.display = "none";
      }
      if (misfireChip) misfireChip.style.display = "inline-flex";
      if (misfireInlineForm) misfireInlineForm.style.display = "none";
      if (misfireFeedbackMsg) misfireFeedbackMsg.style.display = "none";
      if (misfireToolInput) misfireToolInput.value = "";
      currentMisfireQuery = "";
      currentMisfireWrongApp = "";
      commandSection.style.display = "block";
      isDrawerOpen = false;
      badgeText.innerText = "Ready";
      statusDot.style.background = "#38bdf8";
      card.classList.remove("executing");
      progress.classList.remove("active");
      input.value = "";
      selectedIndex = 0;
      updateSuggestions();
      notifyResize();
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
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "p") {
        e.preventDefault();
        window.toggleProjectDrawer();
        return;
      }
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
        if (misfireInlineForm && misfireInlineForm.style.display !== "none") {
          misfireInlineForm.style.display = "none";
          if (misfireChip) misfireChip.style.display = "inline-flex";
          notifyResize();
        } else if (isDrawerOpen) {
          closeDrawers();
        } else {
          window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "close" }));
        }
      }
    });

    micBtn.addEventListener("click", toggleMic);
    modelPill.addEventListener("click", toggleModelDrawer);
    footerModelTag.addEventListener("click", toggleModelDrawer);

    copyBtn.addEventListener("click", () => {
      window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
        action: "copy_to_clipboard",
        text: resultBody.innerText
      }));
      copyBtn.innerText = "Copied!";
      setTimeout(() => { copyBtn.innerText = "Copy"; }, 1500);
    });

    doneBtn.addEventListener("click", closeDrawers);

    function closeDrawers() {
      if (autoCloseTimer) clearTimeout(autoCloseTimer);
      resultDrawer.classList.remove("visible");
      modelDrawer.classList.remove("visible");
      modelDrawer.style.display = "none";
      onboardingDrawer.classList.remove("visible");
      onboardingDrawer.style.display = "none";
      const pDrawer = document.getElementById("project-drawer");
      if (pDrawer) {
        pDrawer.classList.remove("visible");
        pDrawer.style.display = "none";
      }

      if (settingsDrawer) {
        settingsDrawer.classList.remove("visible");
        settingsDrawer.style.display = "none";
      }
      if (misfireFeedbackBar) {
        misfireFeedbackBar.classList.remove("visible");
        misfireFeedbackBar.style.display = "none";
      }
      if (misfireChip) misfireChip.style.display = "inline-flex";
      if (misfireInlineForm) misfireInlineForm.style.display = "none";
      if (misfireFeedbackMsg) misfireFeedbackMsg.style.display = "none";
      if (misfireToolInput) misfireToolInput.value = "";
      currentMisfireQuery = "";
      currentMisfireWrongApp = "";
      commandSection.style.display = "block";
      isDrawerOpen = false;
      badgeText.innerText = "Ready";
      statusDot.style.background = "#38bdf8";
      card.classList.remove("executing");
      updateSuggestions();
      notifyResize();
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
      lastSubmittedQuery = query;
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
      if (payload && payload.action === "open_settings") {
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "get_settings" }));
        return;
      }
      progress.classList.remove("active");
      card.classList.remove("executing");
      commandSection.style.display = "none";
      modelDrawer.classList.remove("visible");
      resultDrawer.classList.add("visible");
      isDrawerOpen = true;

      const respText = payload.response || "Completed successfully.";
      currentResultRaw = respText;

      const action = payload.action || "";
      if (action === "send_message" && payload.recipient) {
        resultBody.innerHTML = `
          <div class="result-math-highlight" style="font-size: 18px; font-weight: 600; color: #f4f4f5; margin-bottom: 4px;">${escapeHtml(payload.recipient)}</div>
          <div class="result-math-sub" style="font-size: 12px; color: #38bdf8; display: flex; align-items: center; gap: 6px;">
            <span>${escapeHtml(payload.email || "")}</span>
            <span style="color: #52525b;">·</span>
            <span style="color: #a1a1aa;">${escapeHtml(payload.client || "Microsoft Outlook")}</span>
            ${payload.subject ? `<span style="color: #52525b;">·</span> <span style="color: #cbd5e1;">"${escapeHtml(payload.subject)}"</span>` : ""}
          </div>
        `;
      } else if (action === "spotify_playlist" && payload.playlist) {
        resultBody.innerHTML = `
          <div class="result-math-highlight" style="font-size: 18px; font-weight: 600; color: #10b981; margin-bottom: 4px;">${escapeHtml(payload.playlist)}</div>
          <div class="result-math-sub" style="font-size: 12px; color: #a1a1aa;">Habitual Playlist · Spotify Native AppleScript</div>
        `;
      } else if (action === "meeting_intent" && payload.tool) {
        const pName = payload.participant && payload.participant.name ? payload.participant.name : "";
        const pRole = payload.participant && payload.participant.role ? payload.participant.role : "";
        const pCompany = payload.participant && payload.participant.company ? payload.participant.company : "";
        let metaHtml = "";
        if (pName) {
          metaHtml = `<span>With <b>${escapeHtml(pName)}</b></span>`;
          if (pRole && pRole !== "Participant") {
            metaHtml += ` <span style="color: #a1a1aa;">(${escapeHtml(pRole)}${pCompany ? ` @ ${escapeHtml(pCompany)}` : ""})</span>`;
          }
        }
        if (payload.topic) {
          metaHtml += `${metaHtml ? `<span style="color: #52525b;">·</span> ` : ""}<span>Topic: <b>${escapeHtml(payload.topic)}</b></span>`;
        }
        resultBody.innerHTML = `
          <div class="result-math-highlight" style="font-size: 18px; font-weight: 600; color: #38bdf8; margin-bottom: 4px;">${escapeHtml(payload.tool)}</div>
          <div class="result-math-sub" style="font-size: 12px; color: #a1a1aa; display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            <span>Meeting Companion · Level 2.5 Ghost Launch</span>
            ${metaHtml ? `<span style="color: #52525b;">·</span> ${metaHtml}` : ""}
          </div>
        `;
      } else if (action.endsWith("_intent") && payload.tool) {
        const intentDisplay = action.replace("_intent", "").toUpperCase();
        resultBody.innerHTML = `
          <div class="result-math-highlight" style="font-size: 18px; font-weight: 600; color: #a78bfa; margin-bottom: 4px;">${escapeHtml(payload.tool)}</div>
          <div class="result-math-sub" style="font-size: 12px; color: #a1a1aa; display: flex; align-items: center; gap: 6px;">
            <span>${escapeHtml(intentDisplay)} Capability · Knowledge Graph Bound</span>
          </div>
        `;
      } else if (action === "calculate" && payload.result) {
        resultBody.innerHTML = `
          <div class="result-math-highlight">${escapeHtml(payload.result)}</div>
          <div class="result-math-sub">${escapeHtml(payload.expression || "")}</div>
        `;
      } else {
        resultBody.innerText = respText;
      }

      const engine = payload.engine || "fast_path";
      const latency = payload.latency_ms ? `${Math.round(payload.latency_ms)}ms` : "";

      if (action === "send_message" || action === "spotify_playlist" || action === "who_is" || action === "memory_summary" || action.endsWith("_intent") || action.startsWith("remember_")) {
        resultEnginePill.innerText = latency ? `Memory · ${latency}` : "Memory";
      } else if (engine === "fast_path") {
        resultEnginePill.innerText = latency ? `Fast-Path · ${latency}` : "Fast-Path";
      } else if (engine === "ollama") {
        resultEnginePill.innerText = latency ? `Ollama · ${latency}` : "Ollama";
      } else {
        resultEnginePill.innerText = latency ? `Done · ${latency}` : "Done";
      }

      badgeText.innerText = "Done";
      statusDot.style.background = "#10b981";

      currentMisfireQuery = payload.query || lastSubmittedQuery || input.value.trim();
      currentMisfireWrongApp = payload.tool || payload.target || payload.client || payload.app || "";
      if (!currentMisfireWrongApp && action) {
        if (action === "meeting_intent") currentMisfireWrongApp = "Meeting Companion";
        else if (action === "spotify_playlist") currentMisfireWrongApp = "Spotify";
        else if (action === "open_app") currentMisfireWrongApp = payload.target || "Application";
        else if (action.endsWith("_intent")) currentMisfireWrongApp = action.replace("_intent", "");
        else currentMisfireWrongApp = "Autonomous Action";
      }

      if (misfireFeedbackBar) {
        misfireFeedbackBar.style.display = "flex";
        misfireFeedbackBar.classList.add("visible");
        if (misfireChip) misfireChip.style.display = "inline-flex";
        if (misfireInlineForm) misfireInlineForm.style.display = "none";
        if (misfireFeedbackMsg) misfireFeedbackMsg.style.display = "none";
        if (misfireToolInput) misfireToolInput.value = "";
        if (misfireLabel) {
          if (currentMisfireWrongApp && currentMisfireWrongApp !== "Autonomous Action") {
            misfireLabel.innerText = `What tool should open instead of ${currentMisfireWrongApp}?`;
          } else {
            misfireLabel.innerText = "What tool should have opened?";
          }
        }
      }

      notifyResize();
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

    const COMPOSIO_APPS_DEF = [
      { toolkit: "googlecalendar", name: "Google Calendar", icon: "🗓️", desc: "Agenda & Zoom/Meet Links" },
      { toolkit: "github", name: "GitHub", icon: "🐙", desc: "Repositories & Open PRs" },
      { toolkit: "gmail", name: "Gmail", icon: "✉️", desc: "Frequent Work Contacts" },
      { toolkit: "slack", name: "Slack", icon: "💬", desc: "Channels & Direct Messages" }
    ];

    let currentComposioStatus = {};

    function normalizeComposioMap(input) {
      const map = {};
      if (Array.isArray(input)) {
        input.forEach(acc => {
          if (acc && acc.toolkit) {
            map[acc.toolkit.toLowerCase()] = acc;
          }
        });
      } else if (input && typeof input === "object") {
        Object.keys(input).forEach(k => {
          map[k.toLowerCase()] = input[k];
        });
      }
      return map;
    }

    function renderComposioCards(containerId, accounts) {
      const container = document.getElementById(containerId);
      if (!container) return;
      container.innerHTML = "";
      const map = normalizeComposioMap(accounts);

      COMPOSIO_APPS_DEF.forEach(app => {
        const acc = map[app.toolkit] || { connected: false, status: "DISCONNECTED" };
        const isConnected = acc.connected || (acc.status === "ACTIVE");
        const isPending = acc.status === "PENDING" || acc.status === "INITIATED";

        const card = document.createElement("div");
        card.className = "composio-card" + (isConnected ? " connected" : (isPending ? " pending" : ""));
        card.id = `${containerId}-${app.toolkit}`;

        let statusBadge = "";
        let actionButtons = "";

        if (isConnected) {
          statusBadge = '<span style="font-size: 9px; color: #34d399; font-weight: 500; margin-right: 4px;">Connected</span>';
          actionButtons = `
            <button class="composio-btn composio-btn-sync" title="Sync now" type="button" onclick="syncComposioApp('${app.toolkit}')">Sync</button>
            <button class="composio-btn composio-btn-disconnect" title="Disconnect & Purge Data" type="button" onclick="disconnectComposioApp('${app.toolkit}')">Disconnect</button>
          `;
        } else if (isPending) {
          statusBadge = '<span style="font-size: 9px; color: #facc15; font-weight: 500; margin-right: 4px;">Pending...</span>';
          actionButtons = `
            <button class="composio-btn composio-btn-connect" type="button" onclick="connectComposioApp('${app.toolkit}')">Authorize</button>
            <button class="composio-btn composio-btn-disconnect" type="button" onclick="disconnectComposioApp('${app.toolkit}')">Cancel</button>
          `;
        } else {
          statusBadge = '<span style="font-size: 9px; color: #64748b; margin-right: 4px;">Not Connected</span>';
          actionButtons = `
            <button class="composio-btn composio-btn-connect" type="button" onclick="connectComposioApp('${app.toolkit}')">Connect</button>
          `;
        }

        card.innerHTML = `
          <div class="composio-info">
            <div class="composio-icon">${app.icon}</div>
            <div class="composio-details">
              <span class="composio-name">${escapeHtml(app.name)}</span>
              <span class="composio-sub">${escapeHtml(app.desc)}</span>
            </div>
          </div>
          <div class="composio-actions">
            ${statusBadge}
            ${actionButtons}
          </div>
        `;
        container.appendChild(card);
      });
    }

    window.connectComposioApp = function(toolkit) {
      window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
        action: "connect_composio_app",
        toolkit: toolkit
      }));
    };

    window.disconnectComposioApp = function(toolkit) {
      window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
        action: "disconnect_composio_app",
        toolkit: toolkit
      }));
    };

    window.syncComposioApp = function(toolkit) {
      window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
        action: "sync_composio_app",
        toolkit: toolkit
      }));
    };

    window.renderComposioStatuses = function(payload) {
      if (payload && payload.accounts) {
        currentComposioStatus = payload.accounts;
      }
      renderComposioCards("onb-composio-grid", currentComposioStatus);
      renderComposioCards("settings-composio-grid", currentComposioStatus);
      const keyBadge = document.getElementById("composio-key-badge");
      if (keyBadge) {
        if (payload && payload.composio_configured) {
          keyBadge.innerHTML = '<span style="color: #10b981; font-weight: 500;">✓ Active</span>';
        } else {
          keyBadge.innerHTML = '<span style="color: #f59e0b; font-weight: 500;">Unconfigured</span>';
        }
      }
      notifyResize();
    };

    window.updateComposioCardStatus = function(toolkit, status, redirectUrl) {
      if (!currentComposioStatus[toolkit]) {
        currentComposioStatus[toolkit] = {};
      }
      currentComposioStatus[toolkit].status = status;
      currentComposioStatus[toolkit].connected = (status === "ACTIVE");
      if (redirectUrl) {
        currentComposioStatus[toolkit].redirect_url = redirectUrl;
      }
      renderComposioCards("onb-composio-grid", currentComposioStatus);
      renderComposioCards("settings-composio-grid", currentComposioStatus);
      notifyResize();
    };

    window.toggleProjectDrawer = function() {
      const pDrawer = document.getElementById("project-drawer");
      if (!pDrawer) return;
      if (pDrawer.classList.contains("visible")) {
        pDrawer.classList.remove("visible");
        pDrawer.style.display = "none";
        isDrawerOpen = false;
        input.focus();
        notifyResize();
      } else {
        closeDrawers();
        pDrawer.style.display = "flex";
        pDrawer.classList.add("visible");
        isDrawerOpen = true;
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
          action: "get_projects"
        }));
        notifyResize();
      }
    };

    window.renderProjectList = function(activeProject, projects) {
      const container = document.getElementById("project-list");
      if (!container) return;
      container.innerHTML = "";
      const projList = Array.isArray(projects) && projects.length > 0 ? projects : ["Personal"];
      projList.forEach(p => {
        const isAct = p.toLowerCase() === (activeProject || "").toLowerCase();
        const pCard = document.createElement("div");
        pCard.className = "project-card" + (isAct ? " active" : "");
        pCard.innerHTML = `
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: ${isAct ? '#38bdf8' : '#71717a'};"></span>
            <span style="font-size: 13px; font-weight: 500; color: #f4f4f5;">${escapeHtml(p)}</span>
          </div>
          <span style="font-size: 11px; color: ${isAct ? '#38bdf8' : '#71717a'};">
            ${isAct ? 'Active' : 'Switch'}
          </span>
        `;
        pCard.addEventListener("click", () => {
          window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
            action: "switch_project",
            project: p
          }));
        });
        container.appendChild(pCard);
      });
      notifyResize();
    };

    window.updateActiveProject = function(projectName) {
      const nameEl = document.getElementById("workspace-name");
      if (nameEl) nameEl.textContent = projectName;
      const pDrawer = document.getElementById("project-drawer");
      if (pDrawer && pDrawer.classList.contains("visible")) {
        pDrawer.classList.remove("visible");
        pDrawer.style.display = "none";
        isDrawerOpen = false;
      }
      input.focus();
      notifyResize();
    };


    window.displayOnboardingDrawer = function(data) {
      if (autoCloseTimer) clearTimeout(autoCloseTimer);
      progress.classList.remove("active");
      card.classList.remove("executing");
      commandSection.style.display = "none";
      resultDrawer.classList.remove("visible");
      resultDrawer.style.display = "none";
      modelDrawer.classList.remove("visible");
      modelDrawer.style.display = "none";
      onboardingDrawer.style.display = "flex";
      onboardingDrawer.classList.add("visible");
      isDrawerOpen = true;

      badgeText.innerText = "Onboarding";
      statusDot.style.background = "#38bdf8";

      if (data && data.user) {
        onbName.value = data.user.name || "";
        onbRole.value = data.user.role || "";
        onbCompany.value = data.user.company || "";
      }
      if (data && data.media_habits) {
        onbPlaylist.value = data.media_habits.focus_playlist || "";
      }
      if (data && data.collaborators && data.collaborators.length > 0) {
        onbCollabs.value = data.collaborators.map(c => `${c.name} (${c.email || "no email"})`).join(", ");
      } else {
        onbCollabs.value = "";
      }

      onbAppsChips.innerHTML = "";
      const apps = (data && data.top_apps && data.top_apps.length > 0) ? data.top_apps : [
        { name: "Google Chrome", category: "browser", is_running: true },
        { name: "Microsoft Outlook", category: "communication", is_running: true },
        { name: "Terminal", category: "developer", is_running: true },
        { name: "ChatGPT", category: "ai_assistant", is_running: true },
        { name: "Spotify", category: "media", is_running: true },
        { name: "Granola", category: "meeting", is_running: true }
      ];

      apps.forEach(app => {
        const chip = document.createElement("div");
        chip.className = "onb-chip active";
        chip.setAttribute("data-app-name", app.name);
        chip.setAttribute("data-app-cat", app.category || "application");
        chip.title = "Click to toggle application binding";
        const icon = { browser: "🌐", communication: "💬", developer: "💻", ai_assistant: "🤖", media: "🎵", meeting: "🗓️", notes: "📝", design: "🎨", tasks: "✅" }[app.category] || "📦";
        chip.innerHTML = `<span>${icon}</span> <span>${escapeHtml(app.name)}</span> <span style="opacity: 0.6; font-size: 10px; margin-left: 2px;">(${escapeHtml(app.category || "app")})</span>`;
        chip.addEventListener("click", () => {
          chip.classList.toggle("active");
        });
        onbAppsChips.appendChild(chip);
      });

      if (data && data.verified) {
        onbStatusBadge.innerText = "✓ Verified Ground Truth";
        onbStatusBadge.style.color = "#34d399";
        onbStatusBadge.style.background = "rgba(16, 185, 129, 0.12)";
      } else {
        onbStatusBadge.innerText = "Ambient Hydrated";
        onbStatusBadge.style.color = "#38bdf8";
        onbStatusBadge.style.background = "rgba(56, 189, 248, 0.12)";
      }

      const accountsOnb = (data && (data.composio_accounts || data.connected_accounts)) || currentComposioStatus;
      renderComposioCards("onb-composio-grid", accountsOnb);

      onbConfirmBtn.innerText = "Confirm & Seal Knowledge Graph";
      onbConfirmBtn.style.background = "#0284c7";
      onbConfirmBtn.disabled = false;
      notifyResize();
      setTimeout(() => {
        onbName.focus();
        onbName.select();
      }, 50);
    };

    window.auraOnboardingSaved = function(result) {
      onbStatusBadge.innerText = "✓ Sealed with Pure Data";
      onbStatusBadge.style.color = "#34d399";
      onbStatusBadge.style.background = "rgba(16, 185, 129, 0.15)";
      onbConfirmBtn.innerText = "✓ Knowledge Graph Sealed";
      onbConfirmBtn.style.background = "#059669";
      badgeText.innerText = "Verified";
      statusDot.style.background = "#10b981";

      const footerOnbText = document.getElementById("footer-onb-text");
      if (footerOnbText) footerOnbText.innerText = "Brain: Verified";
      const footerDot = document.getElementById("onb-footer-dot");
      if (footerDot) footerDot.className = "dot-green";

      setTimeout(() => {
        closeDrawers();
        if (result) {
          window.displayResult({
            action: "onboard_complete",
            response: `✓ Knowledge Graph Verified & Sealed with Pure User Data\n• Identity: ${result.user_name} (${result.user_role} @ ${result.user_company})\n• Work Circle: ${result.collaborators_count} collaborators locked in graph\n• Cluster Isolation: STRICT_DISJOINT Active (Zero Leakage)\n• Intent Grounding: Level 2 & Level 2.5 Active (<0.5ms resolution)`
          });
        }
      }, 1100);
    };

    const onbCloseBtn = document.getElementById("onb-close-btn");
    if (onbCloseBtn) onbCloseBtn.addEventListener("click", closeDrawers);
    onbCancelBtn.addEventListener("click", closeDrawers);

    onboardingDrawer.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        closeDrawers();
      } else if (e.key === "Enter" && !e.shiftKey) {
        if (e.target === onbNewAppName || e.target === onbNewAppCat) {
          e.preventDefault();
          e.stopPropagation();
          if (onbAddAppBtn) onbAddAppBtn.click();
          return;
        }
        e.preventDefault();
        onbConfirmBtn.click();
      }
    });

    if (onbAddAppBtn) {
      onbAddAppBtn.addEventListener("click", () => {
        const appName = onbNewAppName ? onbNewAppName.value.trim() : "";
        const appCat = (onbNewAppCat && onbNewAppCat.value.trim()) ? onbNewAppCat.value.trim() : "developer";
        if (!appName) return;

        // Prevent duplicate chips
        const existingChips = onbAppsChips.querySelectorAll(".onb-chip");
        let alreadyExists = false;
        existingChips.forEach(c => {
          if ((c.getAttribute("data-app-name") || "").toLowerCase() === appName.toLowerCase()) {
            alreadyExists = true;
            c.classList.add("active");
          }
        });

        if (!alreadyExists) {
          const chip = document.createElement("div");
          chip.className = "onb-chip active";
          chip.setAttribute("data-app-name", appName);
          chip.setAttribute("data-app-cat", appCat);
          chip.title = "Click to toggle application binding";
          const icon = { browser: "🌐", communication: "💬", developer: "💻", ai_assistant: "🤖", media: "🎵", meeting: "🗓️", notes: "📝", design: "🎨", tasks: "✅", utility: "⚙️", productivity: "📝" }[appCat] || "📦";
          chip.innerHTML = `<span>${icon}</span> <span>${escapeHtml(appName)}</span> <span style="opacity: 0.6; font-size: 10px; margin-left: 2px;">(${escapeHtml(appCat)})</span>`;
          chip.addEventListener("click", () => {
            chip.classList.toggle("active");
          });
          onbAppsChips.appendChild(chip);
        }
        if (onbNewAppName) {
          onbNewAppName.value = "";
          onbNewAppName.focus();
        }
        if (onbNewAppCat) onbNewAppCat.value = "";
        notifyResize();
      });
    }

    if (onbNewAppName) {
      onbNewAppName.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          e.stopPropagation();
          if (onbAddAppBtn) onbAddAppBtn.click();
        }
      });
    }
    if (onbNewAppCat) {
      onbNewAppCat.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          e.stopPropagation();
          if (onbAddAppBtn) onbAddAppBtn.click();
        }
      });
    }

    onbConfirmBtn.addEventListener("click", () => {
      onbConfirmBtn.innerText = "Sealing Knowledge Graph...";
      onbConfirmBtn.disabled = true;

      const collabsParsed = [];
      const rawCollabs = onbCollabs.value.split(",");
      rawCollabs.forEach(item => {
        const trimmed = item.trim();
        if (!trimmed) return;
        const m = trimmed.match(/^([^(]+)(?:\(([^)]+)\))?$/);
        if (m) {
          collabsParsed.push({
            name: m[1].trim(),
            email: (m[2] || "").trim(),
            role: "Collaborator",
            company: onbCompany.value.trim() || ""
          });
        } else {
          collabsParsed.push({
            name: trimmed,
            email: "",
            role: "Collaborator",
            company: onbCompany.value.trim() || ""
          });
        }
      });

      const activeApps = [];
      const chips = onbAppsChips.querySelectorAll(".onb-chip.active");
      chips.forEach(chip => {
        const appName = chip.getAttribute("data-app-name") || chip.querySelector("span:last-child")?.innerText?.trim();
        const appCat = chip.getAttribute("data-app-cat") || "application";
        if (appName) {
          activeApps.push({ name: appName, category: appCat });
        }
      });

      const profilePayload = {
        action: "save_onboarding",
        profile: {
          user_name: onbName.value.trim(),
          user_role: onbRole.value.trim(),
          user_company: onbCompany.value.trim(),
          playlists: {
            focus: onbPlaylist.value.trim()
          },
          collaborators: collabsParsed,
          connected_apps: activeApps
        }
      };

      window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify(profilePayload));
    });

    footerOnbTag.addEventListener("click", () => {
      if (onboardingDrawer.classList.contains("visible")) {
        closeDrawers();
      } else {
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "get_onboarding_data" }));
      }
    });

    let currentSettingsData = null;

    window.displaySettingsDrawer = function(data) {
      if (autoCloseTimer) clearTimeout(autoCloseTimer);
      progress.classList.remove("active");
      card.classList.remove("executing");
      commandSection.style.display = "none";
      resultDrawer.classList.remove("visible");
      resultDrawer.style.display = "none";
      modelDrawer.classList.remove("visible");
      modelDrawer.style.display = "none";
      onboardingDrawer.classList.remove("visible");
      onboardingDrawer.style.display = "none";
      if (settingsDrawer) {
        settingsDrawer.style.display = "flex";
        settingsDrawer.classList.add("visible");
      }
      isDrawerOpen = true;

      badgeText.innerText = "Settings";
      statusDot.style.background = "#a78bfa";

      currentSettingsData = data || {};
      const user = currentSettingsData.user || {};
      if (settingsName) settingsName.value = user.name || "";
      if (settingsRole) settingsRole.value = user.role || "";
      if (settingsCompany) settingsCompany.value = user.company || "";
      
      const playlists = currentSettingsData.playlists || {};
      if (settingsPlaylist) settingsPlaylist.value = playlists.focus || "";

      renderSettingsApps(currentSettingsData.connected_apps || []);
      renderSettingsCollabs(currentSettingsData.collaborators || []);
      const accountsSet = (currentSettingsData && (currentSettingsData.composio_accounts || currentSettingsData.connected_accounts)) || currentComposioStatus;
      renderComposioCards("settings-composio-grid", accountsSet);
      notifyResize();
    };

    function renderSettingsApps(apps) {
      if (!settingsAppsContainer) return;
      settingsAppsContainer.innerHTML = "";
      if (!apps || apps.length === 0) {
        settingsAppsContainer.innerHTML = '<div style="color: #71717a; font-size: 11px; padding: 4px;">No connected applications yet. Add one below.</div>';
        return;
      }
      apps.forEach(a => {
        const row = document.createElement("div");
        row.className = "settings-collab-row";
        const icon = { browser: "🌐", communication: "💬", developer: "💻", ai_assistant: "🤖", media: "🎵", meeting: "🗓️", notes: "📝", design: "🎨", tasks: "✅" }[a.category] || "📦";
        const intentOrCat = a.intent || a.category || a.role || "App";
        row.innerHTML = `
          <div class="settings-collab-info">
            <span>${icon}</span>
            <span style="font-weight: 500; color: #f4f4f5;">${escapeHtml(a.name)}</span>
            <span style="color: #71717a;">·</span>
            <span style="color: #a1a1aa; font-size: 11px;">Capability: <b style="color: #c4b5fd;">${escapeHtml(intentOrCat)}</b></span>
          </div>
          <button class="settings-del-btn" title="Delete application" data-id="${escapeHtml(a.id || a.name)}">✕</button>
        `;
        const delBtn = row.querySelector(".settings-del-btn");
        delBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
            action: "delete_app",
            identifier: a.id || a.name
          }));
        });
        settingsAppsContainer.appendChild(row);
      });
    }

    function renderSettingsCollabs(collabs) {
      if (!settingsCollabsContainer) return;
      settingsCollabsContainer.innerHTML = "";
      if (!collabs || collabs.length === 0) {
        settingsCollabsContainer.innerHTML = '<div style="color: #71717a; font-size: 11px; padding: 4px;">No team collaborators yet. Add one below.</div>';
        return;
      }
      collabs.forEach(c => {
        const row = document.createElement("div");
        row.className = "settings-collab-row";
        row.innerHTML = `
          <div class="settings-collab-info">
            <span style="font-weight: 500; color: #f4f4f5;">${escapeHtml(c.name)}</span>
            <span style="color: #71717a;">·</span>
            <span style="color: #a1a1aa;">${escapeHtml(c.email || c.role || "Team")}</span>
          </div>
          <button class="settings-del-btn" title="Delete collaborator" data-id="${escapeHtml(c.id || c.name)}">✕</button>
        `;
        const delBtn = row.querySelector(".settings-del-btn");
        delBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
            action: "delete_collaborator",
            identifier: c.id || c.name
          }));
        });
        settingsCollabsContainer.appendChild(row);
      });
    }

    window.auraSettingsSaved = function(result) {
      if (settingsSaveBtn) {
        settingsSaveBtn.innerText = "✓ Saved";
        settingsSaveBtn.style.background = "#059669";
        settingsSaveBtn.disabled = false;
      }
      badgeText.innerText = "Saved";
      statusDot.style.background = "#10b981";
      setTimeout(() => {
        closeDrawers();
      }, 800);
    };

    if (settingsBtn) {
      settingsBtn.addEventListener("click", () => {
        if (settingsDrawer && settingsDrawer.classList.contains("visible")) {
          closeDrawers();
        } else {
          window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "get_settings" }));
        }
      });
    }

    if (settingsCloseBtn) settingsCloseBtn.addEventListener("click", closeDrawers);

    if (settingsAddAppBtn) {
      settingsAddAppBtn.addEventListener("click", () => {
        const name = settingsNewAppName ? settingsNewAppName.value.trim() : "";
        const cat = (settingsNewAppCat && settingsNewAppCat.value.trim()) ? settingsNewAppCat.value.trim() : "developer";
        if (!name) return;
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
          action: "add_app",
          name: name,
          category: cat,
          intent: cat
        }));
        if (settingsNewAppName) settingsNewAppName.value = "";
        if (settingsNewAppCat) settingsNewAppCat.value = "";
      });
    }

    if (settingsAddCollabBtn) {
      settingsAddCollabBtn.addEventListener("click", () => {
        const name = settingsNewName ? settingsNewName.value.trim() : "";
        const email = settingsNewEmail ? settingsNewEmail.value.trim() : "";
        const role = settingsNewRole ? settingsNewRole.value.trim() : "";
        if (!name) return;
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
          action: "add_collaborator",
          name: name,
          email: email,
          role: role,
          company: settingsCompany ? settingsCompany.value.trim() : ""
        }));
        if (settingsNewName) settingsNewName.value = "";
        if (settingsNewEmail) settingsNewEmail.value = "";
        if (settingsNewRole) settingsNewRole.value = "";
      });
    }

    if (settingsSaveBtn) {
      settingsSaveBtn.addEventListener("click", () => {
        settingsSaveBtn.innerText = "Saving...";
        settingsSaveBtn.disabled = true;
        const payload = {
          action: "save_settings",
          settings: {
            user: {
              name: settingsName ? settingsName.value.trim() : "",
              role: settingsRole ? settingsRole.value.trim() : "",
              company: settingsCompany ? settingsCompany.value.trim() : ""
            },
            playlists: {
              focus: settingsPlaylist ? settingsPlaylist.value.trim() : ""
            }
          }
        };
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify(payload));
      });
    }

    if (settingsResetBtn) {
      settingsResetBtn.addEventListener("click", () => {
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "reset_onboarding" }));
      });
    }

    if (settingsDrawer) {
      settingsDrawer.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation();
          closeDrawers();
        } else if (e.key === "Enter" && !e.shiftKey) {
          if (e.target === settingsNewAppName || e.target === settingsNewAppCat) {
            e.preventDefault();
            e.stopPropagation();
            if (settingsAddAppBtn) settingsAddAppBtn.click();
            return;
          }
          if (e.target === settingsNewName || e.target === settingsNewEmail || e.target === settingsNewRole) {
            e.preventDefault();
            e.stopPropagation();
            if (settingsAddCollabBtn) settingsAddCollabBtn.click();
            return;
          }
        }
      });
    }

    if (settingsNewAppName) {
      settingsNewAppName.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          e.stopPropagation();
          if (settingsAddAppBtn) settingsAddAppBtn.click();
        }
      });
    }
    if (settingsNewAppCat) {
      settingsNewAppCat.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          e.stopPropagation();
          if (settingsAddAppBtn) settingsAddAppBtn.click();
        }
      });
    }
    if (settingsNewName) {
      settingsNewName.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          e.stopPropagation();
          if (settingsAddCollabBtn) settingsAddCollabBtn.click();
        }
      });
    }
    if (settingsNewEmail) {
      settingsNewEmail.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          e.stopPropagation();
          if (settingsAddCollabBtn) settingsAddCollabBtn.click();
        }
      });
    }
    if (settingsNewRole) {
      settingsNewRole.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          e.stopPropagation();
          if (settingsAddCollabBtn) settingsAddCollabBtn.click();
        }
      });
    }

    window.updateOnboardingTag = function(isVerified) {
      const footerOnbText = document.getElementById("footer-onb-text");
      const footerDot = document.getElementById("onb-footer-dot");
      if (footerOnbText) {
        footerOnbText.innerText = isVerified ? "Brain: Verified" : "Brain: Setup Required";
      }
      if (footerDot) {
        footerDot.className = isVerified ? "dot-green" : "dot-amber";
      }
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

    function submitMisfireFeedback() {
      const corrected = misfireToolInput ? misfireToolInput.value.trim() : "";
      if (!corrected) return;

      window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
        action: "record_misfire",
        query: currentMisfireQuery,
        wrong_app: currentMisfireWrongApp,
        correct_app: corrected
      }));

      if (misfireInlineForm) misfireInlineForm.style.display = "none";
      if (misfireFeedbackMsg) {
        misfireFeedbackMsg.style.display = "flex";
        if (misfireFeedbackText) {
          misfireFeedbackText.innerText = "Preference updated — Aura learned!";
        }
      }
      badgeText.innerText = "Learned preference";
      statusDot.style.background = "#10b981";
      notifyResize();
    }

    if (misfireChip) {
      misfireChip.addEventListener("click", (e) => {
        e.stopPropagation();
        misfireChip.style.display = "none";
        if (misfireInlineForm) misfireInlineForm.style.display = "flex";
        notifyResize();
        setTimeout(() => {
          if (misfireToolInput) {
            misfireToolInput.focus();
            misfireToolInput.select();
          }
        }, 30);
      });
    }

    if (misfireSubmitBtn) {
      misfireSubmitBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        submitMisfireFeedback();
      });
    }

    if (misfireCancelBtn) {
      misfireCancelBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (misfireInlineForm) misfireInlineForm.style.display = "none";
        if (misfireChip) misfireChip.style.display = "inline-flex";
        notifyResize();
      });
    }

    if (misfireToolInput) {
      misfireToolInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          e.stopPropagation();
          submitMisfireFeedback();
        } else if (e.key === "Escape") {
          e.preventDefault();
          e.stopPropagation();
          if (misfireInlineForm) misfireInlineForm.style.display = "none";
          if (misfireChip) misfireChip.style.display = "inline-flex";
          notifyResize();
        }
      });
    }

    window.auraMisfireRecorded = function(result, message, badge) {
      if (misfireInlineForm) misfireInlineForm.style.display = "none";
      if (misfireFeedbackMsg) {
        misfireFeedbackMsg.style.display = "flex";
        if (misfireFeedbackText) {
          misfireFeedbackText.innerText = message || "Preference updated — Aura learned!";
        }
      }
      badgeText.innerText = badge || "Learned preference";
      statusDot.style.background = "#10b981";
      notifyResize();
    };

    // Dynamic Window Drag & Position Controller (Hover & Drag Anywhere)
    let isDraggingWindow = false;
    let dragStartX = 0;
    let dragStartY = 0;

    function initDraggableWindow() {
      const dragHandle = document.getElementById("drag-handle-bar");
      const headerBar = document.getElementById("header-bar");

      function onDragMouseDown(e) {
        if (e.button !== 0) return; // Only primary mouse button
        if (e.target.closest("input, textarea, button, .action-btn, .mic-btn, .settings-btn, .model-pill-btn, .workspace-pill-btn, #tray, .result-body, #onboarding-drawer, #settings-drawer, #model-drawer, .interactive, .suggestion-item")) {
          return;
        }
        isDraggingWindow = true;
        dragStartX = e.screenX;
        dragStartY = e.screenY;
        document.body.classList.add("dragging");
        e.preventDefault();
      }

      if (dragHandle) dragHandle.addEventListener("mousedown", onDragMouseDown);
      if (headerBar) headerBar.addEventListener("mousedown", onDragMouseDown);

      window.addEventListener("mousemove", (e) => {
        if (!isDraggingWindow) return;
        const dx = e.screenX - dragStartX;
        const dy = e.screenY - dragStartY;
        dragStartX = e.screenX;
        dragStartY = e.screenY;
        if (dx !== 0 || dy !== 0) {
          if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.desktopDom) {
            window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
              action: "drag_window",
              dx: dx,
              dy: dy
            }));
          }
        }
      });

      window.addEventListener("mouseup", () => {
        if (isDraggingWindow) {
          isDraggingWindow = false;
          document.body.classList.remove("dragging");
        }
      });
    }

    initDraggableWindow();

    const workspacePill = document.getElementById("workspace-pill");
    if (workspacePill) {
      workspacePill.addEventListener("click", (e) => {
        e.stopPropagation();
        window.toggleProjectDrawer();
      });
    }

    const saveKeyBtn = document.getElementById("settings-save-key-btn");
    const keyInput = document.getElementById("settings-composio-key");
    if (saveKeyBtn && keyInput) {
      saveKeyBtn.addEventListener("click", () => {
        const val = keyInput.value.trim();
        if (!val) return;
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
          action: "save_composio_api_key",
          api_key: val
        }));
        keyInput.value = "";
        keyInput.placeholder = "comp_••••••••••••";
      });
    }

    const projAddBtn = document.getElementById("project-add-btn");
    const projNewInput = document.getElementById("project-new-name");
    if (projAddBtn && projNewInput) {
      projAddBtn.addEventListener("click", () => {
        const pName = projNewInput.value.trim();
        if (!pName) return;
        window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({
          action: "switch_project",
          project: pName
        }));
        projNewInput.value = "";
      });
      projNewInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          projAddBtn.click();
        }
      });
    }

    updateSuggestions();
    input.focus();

    card.addEventListener("click", (e) => {
      if (!e.target.closest("#mic-btn") &&
          !e.target.closest(".action-btn") &&
          !e.target.closest("#footer-model-tag") &&
          !e.target.closest("#model-pill") &&
          !e.target.closest("#workspace-pill") &&
          !e.target.closest(".model-card") &&
          !e.target.closest("#misfire-feedback-bar") &&
          !e.target.closest("#onboarding-drawer") &&
          !e.target.closest("#project-drawer") &&
          !e.target.closest("#settings-drawer")) {
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
      window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "check_onboarding_status" }));
      window.webkit.messageHandlers.desktopDom.postMessage(JSON.stringify({ action: "get_composio_status" }));
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
            if action == "drag_window":
                dx = float(payload.get("dx", 0))
                dy = float(payload.get("dy", 0))
                self.controller.move_window_by(dx, dy)
            elif action == "submit_query":
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
            elif action == "check_onboarding_status":
                self.controller.check_onboarding_status()
            elif action == "set_model":
                model_name = payload.get("model", "")
                self.controller.on_model_switch(model_name)
            elif action == "get_onboarding_data":
                self.controller.on_get_onboarding_requested()
            elif action == "save_onboarding":
                profile = payload.get("profile", {})
                self.controller.on_save_onboarding(profile)
            elif action == "get_settings":
                self.controller.on_get_settings_requested()
            elif action == "save_settings":
                settings = payload.get("settings", {})
                self.controller.on_save_settings(settings)
            elif action == "add_collaborator":
                self.controller.on_add_collaborator(
                    payload.get("name", ""),
                    payload.get("email", ""),
                    payload.get("role", "Collaborator"),
                    payload.get("company", "")
                )
            elif action == "delete_collaborator":
                self.controller.on_delete_collaborator(payload.get("identifier"))
            elif action == "add_app":
                self.controller.on_add_app(
                    payload.get("name", ""),
                    payload.get("category", "application"),
                    payload.get("intent")
                )
            elif action == "delete_app":
                self.controller.on_delete_app(payload.get("identifier"))
            elif action == "reset_onboarding":
                self.controller.on_reset_onboarding()
            elif action == "copy_to_clipboard":
                text = payload.get("text", "")
                self.controller.copy_text(text)
            elif action == "record_misfire":
                self.controller.on_record_misfire(
                    payload.get("query", ""),
                    payload.get("wrong_app", ""),
                    payload.get("correct_app", "")
                )
            elif action == "connect_composio_app":
                self.controller.on_connect_composio_app(payload.get("toolkit", ""))
            elif action == "disconnect_composio_app":
                self.controller.on_disconnect_composio_app(payload.get("toolkit", ""))
            elif action == "sync_composio_app":
                self.controller.on_sync_composio_app(payload.get("toolkit", ""))
            elif action == "get_composio_status":

                self.controller.on_get_composio_status()
            elif action == "save_composio_api_key":
                self.controller.on_save_composio_api_key(payload.get("api_key", ""))
            elif action == "switch_project":
                self.controller.on_switch_project(payload.get("project", ""))
            elif action == "get_projects":
                self.controller.on_get_projects()
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
        self._force_onboard = False
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

    def move_window_by(self, dx: float, dy: float):
        """Moves the floating Cocoa NSPanel by (dx, dy) screen delta."""
        def _do():
            if self._panel:
                try:
                    import Cocoa
                    frame = self._panel.frame()
                    # In Cocoa screen coordinates: y goes up from bottom of screen.
                    # Dragging down in WebKit (dy > 0) means decreasing frame origin y.
                    new_origin = Cocoa.NSMakePoint(frame.origin.x + dx, frame.origin.y - dy)
                    self._panel.setFrameOrigin_(new_origin)
                except Exception as e:
                    logger.debug(f"move_window_by error: {e}")
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

        # Create frameless floating KeyablePanel capable of accepting keyboard focus and dragging
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

                def isMovable(self):
                    return True

                def isMovableByWindowBackground(self):
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
        self._panel.setMovable_(True)
        self._panel.setBecomesKeyOnlyIfNeeded_(False)
        self._panel.setWorksWhenModal_(True)
        self._panel.setHidesOnDeactivate_(False)
        self._panel.setAcceptsMouseMovedEvents_(True)
        self._panel.setCollectionBehavior_(
            Cocoa.NSWindowCollectionBehaviorCanJoinAllSpaces |
            Cocoa.NSWindowCollectionBehaviorFullScreenAuxiliary
        )

        # Panel Delegate
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

            panel_del_cls = AuraPanelDelegateObjC

        self._panel_delegate = panel_del_cls.alloc().initWithController_(self)
        self._panel.setDelegate_(self._panel_delegate)

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
                        if act == "drag_window":
                            dx = float(payload.get("dx", 0))
                            dy = float(payload.get("dy", 0))
                            self.ctrl.move_window_by(dx, dy)
                        elif act == "submit_query":
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
                        elif act == "check_onboarding_status":
                            self.ctrl.check_onboarding_status()
                        elif act == "set_model":
                            self.ctrl.on_model_switch(payload.get("model", ""))
                        elif act == "get_onboarding_data":
                            self.ctrl.on_get_onboarding_requested()
                        elif act == "save_onboarding":
                            profile = payload.get("profile", {})
                            self.ctrl.on_save_onboarding(profile)
                        elif act == "get_settings":
                            self.ctrl.on_get_settings_requested()
                        elif act == "save_settings":
                            settings = payload.get("settings", {})
                            self.ctrl.on_save_settings(settings)
                        elif act == "add_collaborator":
                            self.ctrl.on_add_collaborator(
                                payload.get("name", ""),
                                payload.get("email", ""),
                                payload.get("role", "Collaborator"),
                                payload.get("company", "")
                            )
                        elif act == "delete_collaborator":
                            self.ctrl.on_delete_collaborator(payload.get("identifier"))
                        elif act == "add_app":
                            self.ctrl.on_add_app(
                                payload.get("name", ""),
                                payload.get("category", "application"),
                                payload.get("intent")
                            )
                        elif act == "delete_app":
                            self.ctrl.on_delete_app(payload.get("identifier"))
                        elif act == "reset_onboarding":
                            self.ctrl.on_reset_onboarding()
                        elif act == "copy_to_clipboard":
                            self.ctrl.copy_text(payload.get("text", ""))
                        elif act == "record_misfire":
                            self.ctrl.on_record_misfire(
                                payload.get("query", ""),
                                payload.get("wrong_app", ""),
                                payload.get("correct_app", "")
                            )
                        elif act == "connect_composio_app":
                            self.ctrl.on_connect_composio_app(payload.get("toolkit", ""))
                        elif act == "disconnect_composio_app":
                            self.ctrl.on_disconnect_composio_app(payload.get("toolkit", ""))
                        elif act == "sync_composio_app":
                            self.ctrl.on_sync_composio_app(payload.get("toolkit", ""))
                        elif act == "get_composio_status":
                            self.ctrl.on_get_composio_status()
                        elif act == "save_composio_api_key":
                            self.ctrl.on_save_composio_api_key(payload.get("api_key", ""))
                        elif act == "switch_project":
                            self.ctrl.on_switch_project(payload.get("project", ""))
                        elif act == "get_projects":
                            self.ctrl.on_get_projects()
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
            is_unverified = False
            if getattr(self, "_force_onboard", False):
                is_unverified = True
            elif self.brain and getattr(self.brain, "memory", None):
                try:
                    is_unverified = not self.brain.memory.is_onboarding_verified()
                except Exception:
                    is_unverified = False
            if is_unverified:
                self.on_get_onboarding_requested()
            else:
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

    def check_onboarding_status(self):
        """Checks if verified onboarding is complete, updates footer tag, and displays drawer if unverified."""
        if not self.brain or not getattr(self.brain, "memory", None):
            return
        try:
            is_ver = self.brain.memory.is_onboarding_verified()
            self.evaluate_js(f"if (window.updateOnboardingTag) {{ window.updateOnboardingTag({json.dumps(is_ver)}); }}")
            if not is_ver:
                self.on_get_onboarding_requested()
        except Exception as e:
            logger.warning(f"Error checking onboarding status: {e}")

    def on_get_onboarding_requested(self):
        """Retrieves verified onboarding profile data and displays the interactive UI drawer."""
        if not self.brain or not getattr(self.brain, "memory", None):
            return
        try:
            profile = self.brain.memory.get_verified_onboarding_profile()
            if hasattr(self.brain, "get_composio_status"):
                try:
                    c_stat = self.brain.get_composio_status()
                    if isinstance(c_stat, dict) and isinstance(c_stat.get("accounts"), dict):
                        profile["composio_accounts"] = c_stat["accounts"]
                except Exception:
                    pass
            self.evaluate_js(f"window.displayOnboardingDrawer({json.dumps(profile)});")
        except Exception as e:
            logger.warning(f"Error fetching onboarding profile: {e}")

    def on_save_onboarding(self, profile: dict):
        """Persists updated onboarding profile directly to Knowledge Graph database."""
        if not self.brain or not getattr(self.brain, "memory", None):
            return
        try:
            res = self.brain.memory.complete_verified_onboarding(profile)
            self.evaluate_js(f"window.auraOnboardingSaved({json.dumps(res)});")
        except Exception as e:
            logger.warning(f"Error saving onboarding profile: {e}")

    def on_get_settings_requested(self):
        """Retrieves user settings & collaborators and displays the interactive Settings drawer."""
        if not self.brain or not getattr(self.brain, "memory", None):
            return
        try:
            settings_data = self.brain.memory.get_user_settings()
            if hasattr(self.brain, "get_composio_status"):
                try:
                    c_stat = self.brain.get_composio_status()
                    if isinstance(c_stat, dict) and isinstance(c_stat.get("accounts"), dict):
                        settings_data["composio_accounts"] = c_stat["accounts"]
                except Exception:
                    pass
            self.evaluate_js(f"window.displaySettingsDrawer({json.dumps(settings_data)});")
        except Exception as e:
            logger.warning(f"Error fetching user settings: {e}")

    def on_save_settings(self, settings: dict):
        """Persists updated settings and updates UI."""
        if not self.brain or not getattr(self.brain, "memory", None):
            return
        try:
            res = self.brain.memory.update_user_settings(settings)
            self.evaluate_js(f"window.auraSettingsSaved({json.dumps(res)});")
        except Exception as e:
            logger.warning(f"Error saving settings: {e}")

    def on_add_collaborator(self, name: str, email: str = "", role: str = "Collaborator", company: str = ""):
        """Adds collaborator in Knowledge Graph and refreshes settings drawer."""
        if not self.brain or not getattr(self.brain, "memory", None):
            return
        try:
            self.brain.memory.add_collaborator(name, email=email, role=role, company=company)
            settings_data = self.brain.memory.get_user_settings()
            self.evaluate_js(f"window.displaySettingsDrawer({json.dumps(settings_data)});")
        except Exception as e:
            logger.warning(f"Error adding collaborator: {e}")

    def on_delete_collaborator(self, identifier: Any):
        """Deletes collaborator in Knowledge Graph and refreshes settings drawer."""
        if not self.brain or not getattr(self.brain, "memory", None):
            return
        try:
            self.brain.memory.delete_collaborator(identifier)
            settings_data = self.brain.memory.get_user_settings()
            self.evaluate_js(f"window.displaySettingsDrawer({json.dumps(settings_data)});")
        except Exception as e:
            logger.warning(f"Error deleting collaborator: {e}")

    def on_add_app(self, name: str, category: str = "application", intent: Optional[str] = None):
        """Adds application in Knowledge Graph and refreshes settings drawer."""
        if not self.brain or not getattr(self.brain, "memory", None):
            return
        try:
            self.brain.memory.add_app(name=name, category=category, intent=intent)
            settings_data = self.brain.memory.get_user_settings()
            self.evaluate_js(f"window.displaySettingsDrawer({json.dumps(settings_data)});")
        except Exception as e:
            logger.warning(f"Error adding app: {e}")

    def on_delete_app(self, identifier: Any):
        """Deletes application from Knowledge Graph and refreshes settings drawer."""
        if not self.brain or not getattr(self.brain, "memory", None):
            return
        try:
            self.brain.memory.delete_app(identifier)
            settings_data = self.brain.memory.get_user_settings()
            self.evaluate_js(f"window.displaySettingsDrawer({json.dumps(settings_data)});")
        except Exception as e:
            logger.warning(f"Error deleting app: {e}")

    def on_reset_onboarding(self):
        """Resets onboarding flag and immediately opens fresh onboarding drawer."""
        if not self.brain or not getattr(self.brain, "memory", None):
            return
        try:
            self.brain.memory.reset_onboarding()
            self.on_get_onboarding_requested()
        except Exception as e:
            logger.warning(f"Error resetting onboarding: {e}")

    def on_record_misfire(self, query: str, wrong_app: str, correct_app: str):
        """Records misfire feedback, applies graph corrections, and updates Omnibar status."""
        logger.info(f"Misfire feedback received: query='{query}', wrong_app='{wrong_app}', correct_app='{correct_app}'")
        if not self.brain or not getattr(self.brain, "memory", None):
            return None
        try:
            try:
                res = self.brain.memory.record_misfire(
                    query,
                    wrong_app,
                    correct_app,
                    user_feedback="User clicked teach aura chip",
                )
            except TypeError:
                res = self.brain.memory.record_misfire(
                    query,
                    wrong_app,
                    correct_app,
                )

            badge = "Learned preference"
            msg = "Preference updated — Aura learned!"
            js = f"""
            if (window.auraMisfireRecorded) {{
                window.auraMisfireRecorded({json.dumps(res, ensure_ascii=False)}, {json.dumps(msg, ensure_ascii=False)}, {json.dumps(badge, ensure_ascii=False)});
            }} else {{
                const b = document.getElementById('badge-text');
                if (b) b.innerText = {json.dumps(badge, ensure_ascii=False)};
                const d = document.getElementById('status-dot');
                if (d) d.style.background = '#10b981';
            }}
            """
            self.evaluate_js(js)
            return res
        except Exception as e:
            logger.warning(f"Error recording misfire in Omnibar: {e}")
            return None

    def _start_composio_polling(self, toolkit: str, connection_id: str):
        """Polls Composio API in background until user completes OAuth in browser."""
        import threading
        def _poll():
            for _ in range(48):  # 48 * 2.5s = 120s
                time.sleep(2.5)
                try:
                    if not self.brain or not hasattr(self.brain, "composio_ingest"):
                        break
                    client = getattr(self.brain.composio_ingest, "client", None)
                    if not client or not hasattr(client, "get_connection_status"):
                        break
                    state = client.get_connection_status(connection_id)
                    st = getattr(state, "status", "")
                    if st in ["ACTIVE", "CONNECTED"]:
                        if hasattr(self.brain, "memory") and hasattr(self.brain.memory, "update_connected_account"):
                            self.brain.memory.update_connected_account(connection_id, status="ACTIVE")
                        if hasattr(self.brain, "sync_composio_app"):
                            self.brain.sync_composio_app(toolkit)
                        self.evaluate_js(f"window.updateComposioCardStatus('{toolkit}', 'ACTIVE', '');")
                        self.on_get_composio_status()
                        break
                    elif st in ["FAILED", "EXPIRED", "REVOKED"]:
                        self.evaluate_js(f"window.updateComposioCardStatus('{toolkit}', 'DISCONNECTED', '');")
                        break
                except Exception as poll_err:
                    logger.debug(f"Composio polling tick error: {poll_err}")
                    break

        t = threading.Thread(target=_poll, daemon=True)
        t.start()
        return t


    def on_connect_composio_app(self, toolkit: str):
        """Initiates Composio OAuth connection and opens default browser with auto-polling."""
        if not self.brain or not hasattr(self.brain, "connect_composio_app"):
            return {"status": "error", "message": "Brain does not support Composio"}
        try:
            res = self.brain.connect_composio_app(toolkit)
            redirect_url = res.get("redirect_url") if isinstance(res, dict) else None
            status = res.get("status", "PENDING") if isinstance(res, dict) else "PENDING"
            conn_id = (res.get("connection_id") or res.get("id")) if isinstance(res, dict) else None
            if redirect_url and str(redirect_url).startswith("http"):
                webbrowser.open(redirect_url)
            self.evaluate_js(f"window.updateComposioCardStatus('{toolkit}', '{status}', '{redirect_url or ''}');")
            if conn_id and status in {"PENDING", "INITIATED", "AWAITING_USER_AUTH"}:
                self._start_composio_polling(toolkit, conn_id)
            return res
        except Exception as e:
            logger.warning(f"Error connecting Composio app {toolkit}: {e}")
            return {"status": "error", "message": str(e)}

    def on_disconnect_composio_app(self, toolkit: str):
        """Disconnects Composio integration and purges its Knowledge Graph data."""
        if not self.brain or not hasattr(self.brain, "disconnect_composio_app"):
            return {"status": "error", "message": "Brain does not support Composio"}
        try:
            res = self.brain.disconnect_composio_app(toolkit)
            self.evaluate_js(f"window.updateComposioCardStatus('{toolkit}', 'DISCONNECTED', '');")
            return res
        except Exception as e:
            logger.warning(f"Error disconnecting Composio app {toolkit}: {e}")
            return {"status": "error", "message": str(e)}

    def on_sync_composio_app(self, toolkit: str):
        """Runs on-demand sync for a connected Composio integration."""
        if not self.brain or not hasattr(self.brain, "sync_composio_app"):
            return {"status": "error", "message": "Brain does not support Composio"}
        try:
            res = self.brain.sync_composio_app(toolkit)
            self.on_get_composio_status()
            return res
        except Exception as e:
            logger.warning(f"Error syncing Composio app {toolkit}: {e}")
            return {"status": "error", "message": str(e)}

    def on_get_composio_status(self):
        """Fetches status of all cloud integrations and updates the UI."""
        if not self.brain or not hasattr(self.brain, "get_composio_status"):
            return {"status": "error", "message": "Brain does not support Composio"}
        try:
            res = self.brain.get_composio_status()
            if isinstance(res, dict):
                self.evaluate_js(f"window.renderComposioStatuses({json.dumps(res)});")
            return res
        except Exception as e:
            logger.warning(f"Error getting Composio status: {e}")
            return {"status": "error", "message": str(e)}

    def on_save_composio_api_key(self, api_key: str):
        """Saves and activates the Composio API key from Settings."""
        if not self.brain or not hasattr(self.brain, "set_composio_api_key"):
            return {"status": "error", "message": "Brain does not support Composio"}
        try:
            res = self.brain.set_composio_api_key(api_key)
            self.on_get_composio_status()
            return res
        except Exception as e:
            logger.warning(f"Error saving Composio API key: {e}")
            return {"status": "error", "message": str(e)}

    def on_switch_project(self, project_name: str):
        """Switches active workspace context."""
        if not self.brain or not hasattr(self.brain, "switch_project"):
            return {"status": "error", "message": "Brain does not support project switching"}
        try:
            res = self.brain.switch_project(project_name)
            self.evaluate_js(f"window.updateActiveProject('{project_name}');")
            return res
        except Exception as e:
            logger.warning(f"Error switching project: {e}")
            return {"status": "error", "message": str(e)}

    def on_get_projects(self):
        """Retrieves active project and project list for the Project Switcher."""
        if not self.brain or not hasattr(self.brain, "get_projects"):
            return {"status": "error", "message": "Brain does not support project switching"}
        try:
            res = self.brain.get_projects()
            act = res.get("active_project", "Personal") if isinstance(res, dict) else "Personal"
            projs = res.get("projects", []) if isinstance(res, dict) else []
            self.evaluate_js(f"window.renderProjectList('{act}', {json.dumps(projs)});")
            return res
        except Exception as e:
            logger.warning(f"Error getting projects: {e}")
            return {"status": "error", "message": str(e)}


    def on_query_submitted(self, query: str):
        """Processes submitted query with zero flicker and expands Result Drawer."""
        logger.info(f"Omnibar query submitted: '{query}'")
        clean_q = (query or "").strip().lower()
        if clean_q in ("/onboard", "onboard", "/onboarding", "onboarding"):
            self.on_get_onboarding_requested()
            return
        if clean_q in ("/settings", "settings", "/config", "config", "open settings", "preferences"):
            self.on_get_settings_requested()
            return
        
        def _execute():
            if not self.brain:
                return

            res = self.brain.execute_intent(query)
            if isinstance(res, dict) and "query" not in res:
                res["query"] = query
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

    def check_or_start_instance(self, command: bytes = b"show\n") -> bool:
        """
        Ensures only a single instance of Aura runs.
        If another instance is active, sends IPC command to bring it to front and returns False.
        """
        import socket
        import os

        socket_path = "/tmp/desktop_dom_aura.sock"

        # Attempt to communicate with already-running instance
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(0.6)
            s.connect(socket_path)
            s.sendall(command)
            s.close()
            logger.info("Aura already running; sent IPC command.")
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
                    if b"onboard" in data:
                        self.show()
                        self.on_get_onboarding_requested()
                    elif b"show" in data or b"toggle" in data:
                        self.show()
                    elif b"hide" in data:
                        self.hide()
                    conn.close()
            except Exception as e:
                logger.debug(f"IPC socket server terminated: {e}")

        t = threading.Thread(target=_ipc_server, daemon=True)
        t.start()
        return True

    def run(self, force_onboard: bool = False):
        """Starts the native macOS Cocoa event loop."""
        self._force_onboard = force_onboard
        if sys.platform == "darwin":
            cmd = b"onboard\n" if force_onboard else b"show\n"
            if not self.check_or_start_instance(cmd):
                if force_onboard:
                    print("Aura is already running. Summoned onboarding drawer to front.")
                else:
                    print("Aura is already running. Summoned existing window to front.")
                return
        self.setup_ui()
        self.start_global_hotkey_listener()
        self.show()
        if self._app:
            self._app.run()
