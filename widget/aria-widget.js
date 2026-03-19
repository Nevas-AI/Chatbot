/**
 * Neva Chat Widget - Embeddable ERP Support Chatbot
 * ======================================================
 * A single-file, dependency-free chat widget that can be embedded
 * on any website with a simple script tag.
 *
 * Configuration via window.NevaConfig (or window.AriaConfig for backwards compatibility):
 *   apiUrl       - Backend API URL (default: "http://localhost:8000")
 *   clientId     - Client slug for multi-tenant routing (default: "default")
 *   botName      - Bot display name (default: "Neva") — auto-loaded from server if clientId set
 *   primaryColor - Theme color (default: "#6366F1") — auto-loaded from server if clientId set
 *   companyName  - Company name (default: "Nevastech") — auto-loaded from server if clientId set
 *   position     - Widget position (default: "bottom-right")
 */
(function () {
  "use strict";

  // ─── Configuration ─────────────────────────────────────
  var userConfig = window.NevaConfig || window.AriaConfig || window.ARIA_CONFIG || window.nevaConfig || {};
  // Support both "serverUrl" and "apiUrl" keys
  if (userConfig.serverUrl && !userConfig.apiUrl) {
    userConfig.apiUrl = userConfig.serverUrl;
  }
  const CONFIG = Object.assign(
    {
      apiUrl: "",
      clientId: "default",
      botName: "Neva",
      primaryColor: "#6366F1",
      companyName: "Nevastech",
      position: "bottom-right",
    },
    userConfig
  );

  // Resolved client_id (UUID) from server — set after loadClientConfig
  let resolvedClientId = null;

  // ─── State ─────────────────────────────────────────────
  let isOpen = false;
  let sessionId = null;
  let unreadCount = 0;
  let hasShownWelcome = false;
  let streamMsgCounter = 0;
  let isDarkMode =
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;

  // Listen for system theme changes
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (e) {
      isDarkMode = e.matches;
      applyTheme();
    });
  }

  // ─── Color Helpers ─────────────────────────────────────
  function hexToHSL(hex) {
    hex = hex.replace("#", "");
    var r = parseInt(hex.substring(0, 2), 16) / 255;
    var g = parseInt(hex.substring(2, 4), 16) / 255;
    var b = parseInt(hex.substring(4, 6), 16) / 255;
    var max = Math.max(r, g, b), min = Math.min(r, g, b);
    var h, s, l = (max + min) / 2;
    if (max === min) { h = s = 0; }
    else {
      var d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      switch (max) {
        case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
        case g: h = ((b - r) / d + 2) / 6; break;
        case b: h = ((r - g) / d + 4) / 6; break;
      }
    }
    return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
  }

  var primaryHSL = hexToHSL(CONFIG.primaryColor);

  // ─── Inject Google Font ───────────────────────────────
  function injectFont() {
    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap";
    document.head.appendChild(link);
  }

  // ─── Inject Styles ─────────────────────────────────────
  function injectStyles() {
    injectFont();
    var style = document.createElement("style");
    style.id = "aria-widget-styles";
    style.textContent = `
      /* ── CSS Variables ── */
      :root {
        --aria-primary: ${CONFIG.primaryColor};
        --aria-primary-hover: hsl(${primaryHSL.h}, ${primaryHSL.s}%, ${Math.max(primaryHSL.l - 8, 10)}%);
        --aria-primary-light: hsl(${primaryHSL.h}, ${primaryHSL.s}%, 95%);
        --aria-primary-glow: hsl(${primaryHSL.h}, ${primaryHSL.s}%, 60%);
        --aria-gradient-start: ${CONFIG.primaryColor};
        --aria-gradient-end: hsl(${(primaryHSL.h + 30) % 360}, ${primaryHSL.s}%, ${primaryHSL.l}%);
        --aria-bg: #ffffff;
        --aria-bg-secondary: #f4f6f9;
        --aria-bg-message: #ffffff;
        --aria-text: #1e1e2e;
        --aria-text-secondary: #8b8fa3;
        --aria-border: #e8ecf1;
        --aria-shadow: 0 20px 60px rgba(0, 0, 0, 0.12), 0 8px 20px rgba(0, 0, 0, 0.08);
        --aria-bubble-shadow: 0 8px 32px rgba(99, 102, 241, 0.35);
        --aria-msg-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        --aria-radius: 20px;
        --aria-font: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      }

      .aria-dark {
        --aria-bg: #1a1b2e;
        --aria-bg-secondary: #12132a;
        --aria-bg-message: #222345;
        --aria-text: #eaeaff;
        --aria-text-secondary: #7b7fa0;
        --aria-border: #2d2e52;
        --aria-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 8px 20px rgba(0, 0, 0, 0.3);
        --aria-bubble-shadow: 0 8px 32px rgba(99, 102, 241, 0.4);
        --aria-msg-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
        --aria-primary-light: hsl(${primaryHSL.h}, ${Math.max(primaryHSL.s - 20, 20)}%, 22%);
      }

      /* ── Reset ── */
      #aria-widget-container * {
        box-sizing: border-box;
        margin: 0;
        padding: 0;
        font-family: var(--aria-font);
      }

      /* ── Chat Bubble ── */
      #aria-chat-bubble {
        position: fixed;
        bottom: 28px;
        right: 28px;
        width: 64px;
        height: 64px;
        border-radius: 50%;
        background: linear-gradient(135deg, var(--aria-gradient-start), var(--aria-gradient-end));
        color: #ffffff;
        border: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: var(--aria-bubble-shadow);
        z-index: 999998;
        transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
        outline: none;
        overflow: hidden;
      }
      #aria-chat-bubble::before {
        content: '';
        position: absolute;
        inset: 0;
        border-radius: 50%;
        background: linear-gradient(135deg, rgba(255,255,255,0.2), transparent);
        opacity: 0;
        transition: opacity 0.3s;
      }
      #aria-chat-bubble:hover {
        transform: scale(1.12) translateY(-2px);
        box-shadow: 0 12px 40px rgba(99, 102, 241, 0.5);
      }
      #aria-chat-bubble:hover::before { opacity: 1; }
      #aria-chat-bubble:active { transform: scale(0.95); }
      #aria-chat-bubble svg {
        width: 28px;
        height: 28px;
        transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
        position: relative;
        z-index: 1;
      }
      #aria-chat-bubble.aria-open svg {
        transform: rotate(90deg) scale(0.9);
      }

      /* ── Pulse ring animation on bubble ── */
      #aria-chat-bubble::after {
        content: '';
        position: absolute;
        inset: -4px;
        border-radius: 50%;
        border: 2px solid var(--aria-primary);
        opacity: 0;
        animation: aria-ring-pulse 3s ease-out infinite;
      }
      #aria-chat-bubble.aria-open::after { animation: none; opacity: 0; }

      @keyframes aria-ring-pulse {
        0% { transform: scale(1); opacity: 0.6; }
        100% { transform: scale(1.4); opacity: 0; }
      }

      /* ── Unread Badge ── */
      #aria-unread-badge {
        position: absolute;
        top: -5px;
        right: -5px;
        background: linear-gradient(135deg, #ef4444, #f97316);
        color: #fff;
        font-size: 11px;
        font-weight: 700;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        display: none;
        align-items: center;
        justify-content: center;
        border: 3px solid var(--aria-bg);
        line-height: 1;
        z-index: 2;
        animation: aria-badge-pop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
      }
      #aria-unread-badge.aria-visible { display: flex; }
      @keyframes aria-badge-pop {
        0% { transform: scale(0); }
        100% { transform: scale(1); }
      }

      /* ── Chat Window ── */
      #aria-chat-window {
        position: fixed;
        bottom: 104px;
        right: 28px;
        width: 400px;
        height: min(580px, calc(100vh - 120px));
        background: var(--aria-bg);
        border-radius: var(--aria-radius);
        box-shadow: var(--aria-shadow);
        display: flex;
        flex-direction: column;
        overflow: hidden;
        z-index: 999999;
        opacity: 0;
        transform: translateY(24px) scale(0.92);
        transition: opacity 0.35s ease, transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
        pointer-events: none;
        border: 1px solid var(--aria-border);
      }
      #aria-chat-window.aria-visible {
        opacity: 1;
        transform: translateY(0) scale(1);
        pointer-events: all;
      }

      /* ── Header ── */
      #aria-chat-header {
        background: linear-gradient(135deg, var(--aria-gradient-start), var(--aria-gradient-end));
        color: #ffffff;
        padding: 20px 22px;
        display: flex;
        align-items: center;
        gap: 14px;
        flex-shrink: 0;
        position: relative;
        overflow: hidden;
      }
      #aria-chat-header::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -20%;
        width: 160px;
        height: 160px;
        border-radius: 50%;
        background: rgba(255,255,255,0.08);
      }
      #aria-chat-header::after {
        content: '';
        position: absolute;
        bottom: -40%;
        left: -10%;
        width: 120px;
        height: 120px;
        border-radius: 50%;
        background: rgba(255,255,255,0.05);
      }
      #aria-bot-avatar {
        width: 46px;
        height: 46px;
        border-radius: 14px;
        background: rgba(255,255,255,0.2);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        flex-shrink: 0;
        position: relative;
        z-index: 1;
        border: 1px solid rgba(255,255,255,0.15);
      }
      #aria-header-info { flex: 1; position: relative; z-index: 1; }
      #aria-header-name {
        font-weight: 700;
        font-size: 16px;
        letter-spacing: 0.3px;
      }
      #aria-header-status {
        font-size: 12.5px;
        opacity: 0.9;
        display: flex;
        align-items: center;
        gap: 6px;
        margin-top: 3px;
        font-weight: 500;
      }
      .aria-status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #34d399;
        display: inline-block;
        animation: aria-pulse 2s ease-in-out infinite;
        box-shadow: 0 0 6px rgba(52, 211, 153, 0.6);
      }
      @keyframes aria-pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(0.85); }
      }
      #aria-close-btn {
        background: rgba(255,255,255,0.15);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        border: 1px solid rgba(255,255,255,0.1);
        color: #fff;
        width: 34px;
        height: 34px;
        border-radius: 10px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.25s;
        flex-shrink: 0;
        position: relative;
        z-index: 1;
      }
      #aria-close-btn:hover {
        background: rgba(255,255,255,0.25);
        transform: rotate(90deg);
      }

      /* ── Messages Area ── */
      #aria-messages {
        flex: 1;
        overflow-y: auto;
        padding: 20px 18px;
        display: flex;
        flex-direction: column;
        gap: 16px;
        background: var(--aria-bg-secondary);
        scroll-behavior: smooth;
      }
      #aria-messages::-webkit-scrollbar { width: 5px; }
      #aria-messages::-webkit-scrollbar-track { background: transparent; }
      #aria-messages::-webkit-scrollbar-thumb {
        background: var(--aria-border);
        border-radius: 4px;
      }
      #aria-messages::-webkit-scrollbar-thumb:hover {
        background: var(--aria-text-secondary);
      }

      /* ── Message Bubbles ── */
      .aria-message {
        display: flex;
        gap: 10px;
        max-width: 82%;
        animation: aria-msgSlide 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
      }
      @keyframes aria-msgSlide {
        from { opacity: 0; transform: translateY(12px) scale(0.97); }
        to { opacity: 1; transform: translateY(0) scale(1); }
      }
      .aria-message.aria-user {
        align-self: flex-end;
        flex-direction: row-reverse;
      }
      .aria-message.aria-bot { align-self: flex-start; }
      .aria-msg-avatar {
        width: 34px;
        height: 34px;
        border-radius: 10px;
        background: var(--aria-primary-light);
        color: var(--aria-primary);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        flex-shrink: 0;
        margin-top: 2px;
        box-shadow: var(--aria-msg-shadow);
      }
      .aria-user .aria-msg-avatar { display: none; }
      .aria-msg-content {
        display: flex;
        flex-direction: column;
        gap: 5px;
      }
      .aria-msg-bubble {
        padding: 12px 16px !important;
        border-radius: 16px;
        font-size: 14px;
        line-height: 1.65;
        color: var(--aria-text);
        word-wrap: break-word;
        overflow-wrap: break-word;
        white-space: pre-wrap;
        letter-spacing: 0.01em;
      }
      .aria-bot .aria-msg-bubble {
        background: var(--aria-bg-message);
        border-bottom-left-radius: 6px;
        box-shadow: var(--aria-msg-shadow);
        border: 1px solid var(--aria-border);
      }
      .aria-user .aria-msg-bubble {
        background: linear-gradient(135deg, var(--aria-gradient-start), var(--aria-gradient-end));
        color: #ffffff;
        border-bottom-right-radius: 6px;
        box-shadow: 0 3px 12px rgba(99, 102, 241, 0.25);
      }
      .aria-msg-time {
        font-size: 11px;
        color: var(--aria-text-secondary);
        padding: 0 6px;
        font-weight: 500;
        letter-spacing: 0.02em;
      }
      .aria-user .aria-msg-time { text-align: right; }

      /* ── Typing Indicator ── */
      .aria-typing {
        display: flex;
        gap: 10px;
        align-self: flex-start;
        max-width: 85%;
        animation: aria-msgSlide 0.35s ease;
      }
      .aria-typing-dots {
        display: flex;
        gap: 5px;
        padding: 14px 18px;
        background: var(--aria-bg-message);
        border-radius: 16px;
        border-bottom-left-radius: 6px;
        align-items: center;
        box-shadow: var(--aria-msg-shadow);
        border: 1px solid var(--aria-border);
      }
      .aria-typing-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--aria-primary);
        opacity: 0.5;
        animation: aria-bounce 1.4s ease-in-out infinite;
      }
      .aria-typing-dot:nth-child(2) { animation-delay: 0.2s; }
      .aria-typing-dot:nth-child(3) { animation-delay: 0.4s; }
      @keyframes aria-bounce {
        0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
        30% { transform: translateY(-8px); opacity: 1; }
      }

      /* ── Quick Replies ── */
      .aria-quick-replies {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 4px 0;
        animation: aria-msgSlide 0.5s ease;
      }
      .aria-quick-reply {
        background: var(--aria-bg);
        color: var(--aria-primary);
        border: 1.5px solid var(--aria-primary);
        padding: 9px 16px !important;
        border-radius: 24px;
        font-size: 13px;
        cursor: pointer;
        transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
        outline: none;
        font-weight: 600;
        letter-spacing: 0.01em;
      }
      .aria-quick-reply:hover {
        background: linear-gradient(135deg, var(--aria-gradient-start), var(--aria-gradient-end));
        color: #fff;
        border-color: transparent;
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(99, 102, 241, 0.25);
      }
      .aria-quick-reply:active {
        transform: translateY(0) scale(0.97);
      }

      /* ── Escalation Card ── */
      .aria-escalation-card {
        background: var(--aria-bg);
        border: 1px solid var(--aria-border);
        border-radius: 16px;
        padding: 18px;
        margin: 4px 0;
        animation: aria-msgSlide 0.4s ease;
        box-shadow: var(--aria-msg-shadow);
      }
      .aria-escalation-title {
        font-weight: 700;
        font-size: 14px;
        margin-bottom: 14px;
        color: var(--aria-text);
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .aria-escalation-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 0;
        font-size: 13.5px;
        color: var(--aria-text);
      }
      .aria-escalation-item a {
        color: var(--aria-primary);
        text-decoration: none;
        font-weight: 600;
        transition: opacity 0.2s;
      }
      .aria-escalation-item a:hover { opacity: 0.8; text-decoration: underline; }
      .aria-escalation-hours {
        font-size: 12px;
        color: var(--aria-text-secondary);
        margin-top: 10px;
        padding-top: 10px;
        border-top: 1px solid var(--aria-border);
        font-weight: 500;
      }

      /* ── Input Bar ── */
      #aria-input-bar {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 14px 18px;
        border-top: 1px solid var(--aria-border);
        background: var(--aria-bg);
        flex-shrink: 0;
      }
      #aria-input-bar::-webkit-scrollbar, 
      #aria-message-input::-webkit-scrollbar
      {
        display: none;
      }
      #aria-message-input {
        flex: 1;
        border: 2px solid var(--aria-border);
        border-radius: 28px;
        padding: 12px 20px;
        font-size: 14px;
        outline: none;
        background: var(--aria-bg-secondary);
        color: var(--aria-text);
        transition: border-color 0.3s, box-shadow 0.3s;
        resize: none;
        max-height: 82px;
        line-height: 1.45;
        font-family: var(--aria-font);
      }
      #aria-message-input::placeholder {
        color: var(--aria-text-secondary);
        font-weight: 400;
      }
      #aria-message-input:focus {
        border-color: var(--aria-primary);
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12);
      }
      #aria-send-btn {
        width: 44px;
        height: 44px;
        border-radius: 14px;
        background: linear-gradient(135deg, var(--aria-gradient-start), var(--aria-gradient-end));
        color: #fff;
        border: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
        flex-shrink: 0;
        outline: none;
        box-shadow: 0 3px 12px rgba(99, 102, 241, 0.25);
      }
      #aria-send-btn:hover {
        transform: scale(1.08) translateY(-1px);
        box-shadow: 0 5px 18px rgba(99, 102, 241, 0.35);
      }
      #aria-send-btn:active { transform: scale(0.94); }
      #aria-send-btn:disabled {
        opacity: 0.4;
        cursor: not-allowed;
        transform: none;
        box-shadow: none;
      }
      #aria-send-btn svg { width: 18px; height: 18px; }

      /* ── Human Support Button ── */
      #aria-human-btn {
        display: none;
        width: 100%;
        padding: 10px;
        background: var(--aria-bg-secondary);
        color: var(--aria-text);
        border: none;
        border-top: 1px solid var(--aria-border);
        cursor: pointer;
        font-size: 13px;
        font-weight: 600;
        text-align: center;
        transition: background 0.3s;
      }
      #aria-human-btn:hover {
        background: var(--aria-border);
      }
      .aria-working-hours #aria-human-btn {
        display: block;
      }

      /* ── New Chat Button ── */
      #aria-new-chat-btn {
        width: 100%;
        padding: 12px;
        border-radius: 24px;
        background: linear-gradient(135deg, var(--aria-gradient-start), var(--aria-gradient-end));
        color: #fff;
        border: none;
        cursor: pointer;
        display: none;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        font-weight: 600;
        transition: all 0.25s ease;
        box-shadow: 0 3px 12px rgba(99, 102, 241, 0.25);
      }
      #aria-new-chat-btn.aria-visible { display: flex; }
      #aria-new-chat-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 18px rgba(99, 102, 241, 0.35);
      }
      #aria-new-chat-btn:active { transform: translateY(0) scale(0.98); }

      /* ── Powered By ── */
      #aria-powered {
        text-align: center;
        padding: 8px;
        font-size: 11px;
        color: var(--aria-text-secondary);
        background: var(--aria-bg);
        font-weight: 500;
        letter-spacing: 0.02em;
        opacity: 0.6;
      }

      /* ── Mobile Responsive ── */
      @media (max-width: 480px) {
        #aria-chat-window {
          width: calc(100vw - 16px);
          height: calc(100vh - 100px);
          bottom: 84px;
          right: 8px;
          border-radius: 16px;
        }
        #aria-chat-bubble {
          bottom: 18px;
          right: 18px;
        }
      }
    `;
    document.head.appendChild(style);
  }

  // ─── Build Widget DOM ──────────────────────────────────
  function buildWidget() {
    // Container
    var container = document.createElement("div");
    container.id = "aria-widget-container";
    if (isDarkMode) container.classList.add("aria-dark");

    // Chat Bubble Button
    var bubble = document.createElement("button");
    bubble.id = "aria-chat-bubble";
    bubble.setAttribute("aria-label", "Open chat");
    bubble.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
      <span id="aria-unread-badge">0</span>
    `;

    // Chat Window
    var chatWindow = document.createElement("div");
    chatWindow.id = "aria-chat-window";
    chatWindow.innerHTML = `
      <div id="aria-chat-header">
        <div id="aria-bot-avatar">${CONFIG._logoUrl ? '<img src="' + CONFIG.apiUrl + CONFIG._logoUrl + '" alt="bot" style="width:100%;height:100%;border-radius:50%;object-fit:cover;">' : '🤖'}</div>
        <div id="aria-header-info">
          <div id="aria-header-name">${escapeHtml(CONFIG.botName)}</div>
          <div id="aria-header-status">
            <span class="aria-status-dot"></span>
            Online
          </div>
        </div>
        <button id="aria-close-btn" aria-label="Close chat">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      <div id="aria-messages"></div>
      
      
      <div id="aria-input-bar">
        <textarea id="aria-message-input" placeholder="Type your message..." rows="1"></textarea>
        <button id="aria-send-btn" aria-label="Send message">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
        <button id="aria-new-chat-btn" aria-label="Start new chat">Start New Chat</button>
      </div>
      <div id="aria-powered">Powered by ${escapeHtml(CONFIG.botName)} AI</div>
    `;

    container.appendChild(chatWindow);
    container.appendChild(bubble);
    document.body.appendChild(container);
  }

  // ─── Event Handlers ────────────────────────────────────
  function attachEvents() {
    var bubble = document.getElementById("aria-chat-bubble");
    var closeBtn = document.getElementById("aria-close-btn");
    var sendBtn = document.getElementById("aria-send-btn");
    var newChatBtn = document.getElementById("aria-new-chat-btn");
    var humanBtn = document.getElementById("aria-human-btn");
    var input = document.getElementById("aria-message-input");

    bubble.addEventListener("click", toggleChat);
    closeBtn.addEventListener("click", toggleChat);
    sendBtn.addEventListener("click", sendMessage);
    newChatBtn.addEventListener("click", startNewChat);

    humanBtn.addEventListener("click", function () {
      humanBtn.style.display = "none";
      addUserMessage("I want to speak with human support");
      showTyping();
      var sendBtn = document.getElementById("aria-send-btn");
      sendBtn.disabled = true;

      streamChat("/connect_human_support_now")
        .catch(function (err) {
          console.error("Aria chat error:", err);
          hideTyping();
          addBotMessage("I'm sorry, I'm having trouble connecting. Please try again later.");
        })
        .finally(function () {
          sendBtn.disabled = false;
        });
    });

    // Send on Enter (Shift+Enter for new line)
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    // Auto-resize textarea
    input.addEventListener("input", function () {
      this.style.height = "auto";
      this.style.height = Math.min(this.scrollHeight, 82) + "px";
    });
  }

  function toggleChat() {
    isOpen = !isOpen;
    var chatWindow = document.getElementById("aria-chat-window");
    var bubble = document.getElementById("aria-chat-bubble");

    if (isOpen) {
      chatWindow.classList.add("aria-visible");
      bubble.classList.add("aria-open");
      clearUnread();

      // Show welcome message on first open
      if (!hasShownWelcome) {
        hasShownWelcome = true;
        showWelcomeMessage();
      }

      // Focus input
      setTimeout(function () {
        document.getElementById("aria-message-input").focus();
      }, 350);
    } else {
      chatWindow.classList.remove("aria-visible");
      bubble.classList.remove("aria-open");
    }
  }

  // ─── Messages ──────────────────────────────────────────
  function showWelcomeMessage() {
    addBotMessage("Hi! 👋 I'm " + CONFIG.botName + ", your ERP assistant at " + CONFIG.companyName + ". I can help you with Microsoft Dynamics 365, ERP solutions, and more. What would you like to know?");
    showQuickReplies([
      "What is Business Central?",
      "ERP implementation",
      "Request a demo",
      "Contact us",
    ]);
  }

  function addBotMessage(text) {
    var messagesEl = document.getElementById("aria-messages");
    var msgDiv = createMessageElement("bot", text);
    messagesEl.appendChild(msgDiv);
    scrollToBottom();

    if (!isOpen) {
      unreadCount++;
      updateBadge();
    }
  }

  function addUserMessage(text) {
    var messagesEl = document.getElementById("aria-messages");
    var msgDiv = createMessageElement("user", text);
    messagesEl.appendChild(msgDiv);
    scrollToBottom();
  }

  function createMessageElement(type, text) {
    var wrapper = document.createElement("div");
    wrapper.className = "aria-message aria-" + type;

    var now = new Date();
    var timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    var html = "";
    if (type === "bot") {
      var logoUrl = CONFIG._logoUrl ? (CONFIG.apiUrl + CONFIG._logoUrl) : '';
      if (logoUrl) {
        html += '<div class="aria-msg-avatar"><img src="' + logoUrl + '" alt="bot" style="width:24px;height:24px;border-radius:50%;object-fit:cover;"></div>';
      } else {
        html += '<div class="aria-msg-avatar">🤖</div>';
      }
    }
    html += '<div class="aria-msg-content">';
    html += '<div class="aria-msg-bubble">' + formatMessage(text) + "</div>";
    html += '<span class="aria-msg-time">' + timeStr + "</span>";
    html += "</div>";

    wrapper.innerHTML = html;
    return wrapper;
  }

  function formatMessage(text) {
    // Basic markdown-like formatting
    var escaped = escapeHtml(text);
    // Bold: **text**
    escaped = escaped.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    // Links: autolink URLs
    escaped = escaped.replace(
      /(https?:\/\/[^\s<]+)/g,
      '<a href="$1" target="_blank" rel="noopener" style="color:inherit;text-decoration:underline;font-weight:500;">$1</a>'
    );
    // Email links
    escaped = escaped.replace(
      /([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g,
      '<a href="mailto:$1" style="color:inherit;text-decoration:underline;font-weight:500;">$1</a>'
    );
    // Newlines
    escaped = escaped.replace(/\n/g, "<br>");
    return escaped;
  }

  // ─── Quick Replies ─────────────────────────────────────
  function showQuickReplies(options) {
    var messagesEl = document.getElementById("aria-messages");
    var wrapper = document.createElement("div");
    wrapper.className = "aria-quick-replies";

    options.forEach(function (text) {
      var btn = document.createElement("button");
      btn.className = "aria-quick-reply";
      btn.textContent = text;
      btn.addEventListener("click", function () {
        // Remove quick replies after selection
        wrapper.remove();
        // Send as user message
        document.getElementById("aria-message-input").value = text;
        sendMessage();
      });
      wrapper.appendChild(btn);
    });

    messagesEl.appendChild(wrapper);
    scrollToBottom();
  }

  // ─── Escalation Card ──────────────────────────────────
  function showEscalationCard(data) {
    var messagesEl = document.getElementById("aria-messages");
    var card = document.createElement("div");
    card.className = "aria-escalation-card";

    var email = data.email || "support@yourcompany.com";
    var phone = data.phone || "+91-XXXXXXXXXX";
    var hours = data.business_hours || "Mon-Fri 9AM-6PM IST";

    card.innerHTML = `
      <div class="aria-escalation-title">🧑‍💼 Connecting you to our team...</div>
      <div class="aria-escalation-item">
        📧 <a href="mailto:${escapeHtml(email)}">${escapeHtml(email)}</a>
      </div>
      <div class="aria-escalation-item">
        📞 <a href="tel:${escapeHtml(phone)}">${escapeHtml(phone)}</a>
      </div>
      <div class="aria-escalation-hours">
        🕐 Business Hours: ${escapeHtml(hours)}
      </div>
    `;

    messagesEl.appendChild(card);
    scrollToBottom();
  }

  // ─── Typing Indicator ─────────────────────────────────
  function showTyping() {
    var messagesEl = document.getElementById("aria-messages");
    var typing = document.createElement("div");
    typing.className = "aria-typing";
    typing.id = "aria-typing-indicator";
    typing.innerHTML = `
      <div class="aria-msg-avatar">${CONFIG._logoUrl ? '<img src="' + CONFIG.apiUrl + CONFIG._logoUrl + '" alt="bot" style="width:24px;height:24px;border-radius:50%;object-fit:cover;">' : '🤖'}</div>
      <div class="aria-typing-dots">
        <div class="aria-typing-dot"></div>
        <div class="aria-typing-dot"></div>
        <div class="aria-typing-dot"></div>
      </div>
    `;
    messagesEl.appendChild(typing);
    scrollToBottom();
  }

  function hideTyping() {
    var el = document.getElementById("aria-typing-indicator");
    if (el) el.remove();
  }

  // ─── Streaming Bot Message ─────────────────────────────
  function createStreamingMessage() {
    streamMsgCounter++;
    var currentId = "aria-streaming-bubble-" + streamMsgCounter;

    var messagesEl = document.getElementById("aria-messages");
    var wrapper = document.createElement("div");
    wrapper.className = "aria-message aria-bot";

    var now = new Date();
    var timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    wrapper.innerHTML = `
      <div class="aria-msg-avatar">${CONFIG._logoUrl ? '<img src="' + CONFIG.apiUrl + CONFIG._logoUrl + '" alt="bot" style="width:24px;height:24px;border-radius:50%;object-fit:cover;">' : '🤖'}</div>
      <div class="aria-msg-content">
        <div class="aria-msg-bubble" id="${currentId}"></div>
        <span class="aria-msg-time">${timeStr}</span>
      </div>
    `;

    messagesEl.appendChild(wrapper);
    scrollToBottom();
    return document.getElementById(currentId);
  }

  // ─── Send Message ──────────────────────────────────────
  function sendMessage() {
    var input = document.getElementById("aria-message-input");
    var text = input.value.trim();
    if (!text) return;

    // Clear input and reset height
    input.value = "";
    input.style.height = "auto";

    // Add user message to UI
    addUserMessage(text);

    // Show typing indicator
    showTyping();

    // Disable send button while processing
    var sendBtn = document.getElementById("aria-send-btn");
    sendBtn.disabled = true;

    // Call API with SSE streaming
    streamChat(text)
      .catch(function (err) {
        console.error("Aria chat error:", err);
        hideTyping();
        addBotMessage("I'm sorry, I'm having trouble connecting. Please try again later.");
      })
      .finally(function () {
        sendBtn.disabled = false;
        input.focus();
      });
  }

  function handleChatClosed() {
    var input = document.getElementById("aria-message-input");
    var sendBtn = document.getElementById("aria-send-btn");
    var newChatBtn = document.getElementById("aria-new-chat-btn");
    var humanBtn = document.getElementById("aria-human-btn");

    input.style.display = "none";
    sendBtn.style.display = "none";
    if (humanBtn) humanBtn.style.display = "none";
    newChatBtn.classList.add("aria-visible");
  }

  function startNewChat() {
    var input = document.getElementById("aria-message-input");
    var sendBtn = document.getElementById("aria-send-btn");
    var newChatBtn = document.getElementById("aria-new-chat-btn");
    var humanBtn = document.getElementById("aria-human-btn");
    var messagesEl = document.getElementById("aria-messages");

    // Reset UI
    input.style.display = "block";
    sendBtn.style.display = "flex";
    newChatBtn.classList.remove("aria-visible");
    if (humanBtn) humanBtn.style.display = "";

    // Clear state
    messagesEl.innerHTML = "";
    sessionId = null;

    // Start fresh
    showWelcomeMessage();
    input.focus();
  }

  // ─── API Communication (SSE) ───────────────────────────
  async function streamChat(message) {
    var body = JSON.stringify({
      message: message,
      session_id: sessionId,
      client_id: resolvedClientId || CONFIG.clientId,
      page_url: window.location.href,
    });

    try {
      var response = await fetch(CONFIG.apiUrl + "/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body,
      });

      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }

      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var streamBubble = null;
      var fullText = "";
      var isEscalation = false;

      hideTyping();

      while (true) {
        var result = await reader.read();
        if (result.done) break;

        var chunk = decoder.decode(result.value, { stream: true });
        var lines = chunk.split("\n");

        for (var i = 0; i < lines.length; i++) {
          var line = lines[i].trim();
          if (!line.startsWith("data: ")) continue;

          var dataStr = line.substring(6);
          if (dataStr === "[DONE]") continue;

          try {
            var data = JSON.parse(dataStr);

            // Update session ID from server
            if (data.session_id) sessionId = data.session_id;

            if (data.type === "escalation") {
              isEscalation = true;
              addBotMessage(data.content);
              if (data.escalation_data) {
                showEscalationCard(data.escalation_data);
              }
            } else if (data.type === "token") {
              if (!streamBubble) {
                streamBubble = createStreamingMessage();
              }
              fullText += data.content;
              streamBubble.innerHTML = formatMessage(fullText);
              scrollToBottom();
            } else if (data.type === "chat_closed") {
              addBotMessage(data.content);
              handleChatClosed();
            } else if (data.type === "error") {
              addBotMessage(data.content);
            }
          } catch (parseErr) {
            // Skip malformed JSON
          }
        }
      }
    } catch (err) {
      hideTyping();
      addBotMessage("I'm sorry, I couldn't reach the server. Please check your connection and try again.");
      console.error("Aria SSE error:", err);
    }
  }

  // ─── Utility Functions ─────────────────────────────────
  function scrollToBottom() {
    var messagesEl = document.getElementById("aria-messages");
    if (messagesEl) {
      setTimeout(function () {
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }, 50);
    }
  }

  function updateBadge() {
    var badge = document.getElementById("aria-unread-badge");
    if (badge) {
      badge.textContent = unreadCount;
      if (unreadCount > 0) {
        badge.classList.add("aria-visible");
      } else {
        badge.classList.remove("aria-visible");
      }
    }
  }

  function clearUnread() {
    unreadCount = 0;
    updateBadge();
  }

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
  }

  function isWorkingHours() {
    var now = new Date();
    var utc = now.getTime() + (now.getTimezoneOffset() * 60000);
    // IST is UTC + 5:30
    var istTime = new Date(utc + (3600000 * 5.5));
    var day = istTime.getDay(); // 0 is Sunday, 1 is Monday ... 6 is Saturday
    var hour = istTime.getHours();

    // Mon-Fri 9AM to 6PM
    if (day >= 1 && day <= 5 && hour >= 9 && hour < 18) {
      return true;
    }
    return false;
  }

  function applyTheme() {
    var container = document.getElementById("aria-widget-container");
    if (container) {
      if (isDarkMode) {
        container.classList.add("aria-dark");
      } else {
        container.classList.remove("aria-dark");
      }

      if (isWorkingHours()) {
        container.classList.add("aria-working-hours");
      }
    }
  }

  // ─── Initialize ────────────────────────────────────────
  function init() {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", bootstrap);
    } else {
      bootstrap();
    }
  }

  async function loadClientConfig() {
    try {
      var resp = await fetch(CONFIG.apiUrl + "/api/widget/config/" + encodeURIComponent(CONFIG.clientId));
      if (resp.ok) {
        var data = await resp.json();
        // Apply server branding (only override if user didn't set custom values)
        if (data.client_id) resolvedClientId = data.client_id;
        if (data.bot_name) CONFIG.botName = data.bot_name;
        if (data.primary_color) CONFIG.primaryColor = data.primary_color;
        if (data.company_name) CONFIG.companyName = data.company_name;
        if (data.welcome_msg) CONFIG._welcomeMsg = data.welcome_msg;
        if (data.logo_url) CONFIG._logoUrl = data.logo_url;
        // Recompute color variables
        primaryHSL = hexToHSL(CONFIG.primaryColor);
      }
    } catch (e) {
      console.warn("Neva Widget: Could not load client config, using defaults.", e);
    }
  }

  async function bootstrap() {
    // Load client branding from server first
    await loadClientConfig();
    injectStyles();
    buildWidget();
    attachEvents();
    applyTheme();
    console.log(
      "%c" + CONFIG.botName + " Chat Widget loaded ✓ (client: " + CONFIG.clientId + ")",
      "color: " + CONFIG.primaryColor + "; font-weight: bold; font-size: 12px;"
    );
  }

  init();
})();
