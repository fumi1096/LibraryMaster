/**
 * keyboard.js — 虚拟键盘 (simple-keyboard)
 *
 * 基于 simple-keyboard + simple-keyboard-layouts
 * 英文 QWERTY / 中文拼音候选 / 预览窗 / 连续输入
 */
const Keyboard = (function() {
  'use strict';

  var instance = null;
  var isVisible = false;
  var currentLang = 'cn';
  var currentInput = null;
  var showTime = 0;

  var SK = (typeof SimpleKeyboard !== 'undefined')
    ? (SimpleKeyboard.default || SimpleKeyboard.SimpleKeyboard || SimpleKeyboard)
    : null;

  if (!SK || typeof SK !== 'function') {
    console.error('[kb] SimpleKeyboard load failed');
    return { init: function(){}, show: function(){}, hide: function(){}, toggle: function(){} };
  }

  function getConfig(lang) {
    var src = lang === 'cn' ? ChineseLayout : EnglishLayout;
    var ly = JSON.parse(JSON.stringify(src.layout));
    ly.default[4] = '{lang} {space} {hide}';
    ly.shift[4]   = '{lang} {space} {hide}';
    return {
      layout: ly,
      layoutCandidates: src.layoutCandidates || {},
      enableLayoutCandidates: !!(lang === 'cn' && src.layoutCandidates),
      display: {
        '{bksp}': '\u232B', '{tab}': '\u21B9', '{lock}': '\u21EA',
        '{enter}': '\u21B5', '{shift}': '\u21E7', '{space}': ' ',
        '{lang}': lang === 'cn' ? '\u4E2D' : 'EN', '{hide}': '\u2192'
      }
    };
  }

  function activeInput() {
    if (currentInput && document.activeElement === currentInput) return currentInput;
    var ae = document.activeElement;
    if (ae && (ae.id === 'chatInput' || ae.id === 'searchInput')) { currentInput = ae; return ae; }
    // 不 fallback — 保持 currentInput 不变
    return currentInput;
  }

  function updatePreview(text) {
    var el = document.getElementById('kbPreviewText');
    if (el) el.textContent = text || '';
  }

  function createInstance() {
    if (instance) { try { instance.destroy(); } catch(e){} }

    var cfg = getConfig(currentLang);
    instance = new SK({
      layout: cfg.layout,
      layoutCandidates: cfg.layoutCandidates,
      enableLayoutCandidates: cfg.enableLayoutCandidates,
      layoutCandidatesPageSize: 10,
      display: cfg.display,
      theme: 'hg-theme-default',
      useMouseEvents: true,
      disableButtonHold: true,

      onChange: function(text) {
        var inp = activeInput();
        if (inp) {
          inp.value = text;
          inp.dispatchEvent(new Event('input', { bubbles: true }));
        }
        updatePreview(text);
      },

      onKeyPress: function(btn) {
        if (btn === '{lang}') {
          currentLang = currentLang === 'cn' ? 'en' : 'cn';
          var c2 = getConfig(currentLang);
          instance.setOptions({
            layout: c2.layout,
            layoutCandidates: c2.layoutCandidates,
            enableLayoutCandidates: c2.enableLayoutCandidates,
            display: c2.display
          });
          return;
        }
        if (btn === '{hide}') { hide(); return; }
        if (btn === '{enter}') { doSend(); return; }
      }
    });

    // 候选词点击不触发隐藏
    setTimeout(function() {
      var kb = document.getElementById('keyboard');
      if (!kb) return;
      var btns = kb.querySelectorAll('.hg-button');
      for (var i = 0; i < btns.length; i++) {
        (function(b) {
          var skb = b.getAttribute('data-skbtn');
          if (skb === '{hide}') {
            b.addEventListener('mousedown', function(e) { e.stopPropagation(); e.preventDefault(); hide(); });
            b.addEventListener('touchstart', function(e) { e.stopPropagation(); e.preventDefault(); hide(); });
          }
          if (skb === '{lang}') {
            var doLang = function(e) {
              e.stopPropagation(); e.preventDefault();
              currentLang = currentLang === 'cn' ? 'en' : 'cn';
              var c3 = getConfig(currentLang);
              instance.setOptions({ layout: c3.layout, layoutCandidates: c3.layoutCandidates, enableLayoutCandidates: c3.enableLayoutCandidates, display: c3.display });
            };
            b.addEventListener('mousedown', doLang);
            b.addEventListener('touchstart', doLang);
          }
        })(btns[i]);
      }
      // 候选词条点击阻止冒泡
      var candidates = document.querySelectorAll('.hg-candidateBox, .hg-candidate-box, .hg-candidate-box-list li');
      for (var j = 0; j < candidates.length; j++) {
        candidates[j].addEventListener('mousedown', function(e) { e.stopPropagation(); });
        candidates[j].addEventListener('touchstart', function(e) { e.stopPropagation(); });
      }
    }, 150);
  }

  function doSend() {
    var inp = activeInput();
    if (!inp) return;
    var text = inp.value.trim();
    if (text && typeof App !== 'undefined' && App.sendUserMessage) {
      App.sendUserMessage(text);
      inp.value = '';
      if (instance) instance.clearInput();
      updatePreview('');
    }
  }

  function show() {
    var ov = document.getElementById('keyboardOverlay');
    if (!ov) return;

    if (!instance) { createInstance(); }
    else {
      var inp = activeInput();
      if (inp) { instance.setInput(inp.value); updatePreview(inp.value); }
    }

    ov.style.display = 'block';
    isVisible = true;
    showTime = Date.now();
  }

  function hide() {
    var ov = document.getElementById('keyboardOverlay');
    if (!ov) return;
    ov.style.display = 'none';
    ov.classList.remove('active');
    isVisible = false;
    if (currentInput) currentInput.blur();
  }

  function initAutoHide() {
    document.addEventListener('click', function(e) {
      if (!isVisible) return;
      if (Date.now() - showTime < 800) return;
      if (e.target && (e.target.id === 'chatInput' || e.target.id === 'searchInput')) return;
      var ov = document.getElementById('keyboardOverlay');
      if (ov && ov.contains(e.target)) return;
      // 候选词条区域不隐藏
      if (e.target && (e.target.closest('.hg-candidateBox') || e.target.closest('.hg-candidate-box'))) return;
      var footer = document.querySelector('footer');
      if (footer && footer.contains(e.target)) return;
      hide();
    });
  }

  function syncToInput(inp) {
    currentInput = inp;
    if (instance && inp) {
      instance.setInput(inp.value);
      instance.clearInput();
      instance.setInput(inp.value);
    }
    updatePreview(inp ? inp.value : '');
  }

  function init() {
    initAutoHide();
    var ci = document.getElementById('chatInput');
    var si = document.getElementById('searchInput');
    if (ci) ci.addEventListener('focus', function() { syncToInput(ci); show(); });
    if (si) si.addEventListener('focus', function() { syncToInput(si); show(); });
  }

  return { init: init, show: show, hide: hide, toggle: function() { isVisible ? hide() : show(); } };
})();

document.addEventListener('DOMContentLoaded', function() {
  Keyboard.init();
  var dbg = document.getElementById('kb-debug');
  if (dbg) { dbg.className = 'init-ok'; dbg.title = 'Keyboard ready'; }
});
