/**
 * voice.js — 语音输入（长按录音 → 宿主机 relay）
 *
 * WebKit2GTK 不支持 getUserMedia，改用宿主机 voice_relay.py 的 /record 端点
 * 长按 (>500ms) → 调用 relay 录音 → 讯飞 ASR → 填入输入框
 * 短按 (<300ms) → 聚焦输入框，弹出键盘
 */
const Voice = (function() {
  'use strict';

  var mediaRecorder = null;
  var audioChunks = [];
  var isRecording = false;
  var pressTimer = null;
  var pressStartTime = 0;
  var isLongPress = false;

  // 宿主机语音中继地址（Docker 内通过 host.docker.internal 访问宿主机端口）
  var RELAY_URL = '/api/voice/record';

  function init() {
    // 尝试自动探测 relay 地址
    fetch('/api/config').then(function(r) { return r.json(); }).then(function(cfg) {
      if (cfg.voice_relay_url) RELAY_URL = cfg.voice_relay_url;
    }).catch(function() {});

    var btn = App.DOM.voiceBtn;

    btn.addEventListener('mousedown', onPressStart);
    btn.addEventListener('mouseup', onPressEnd);
    btn.addEventListener('mouseleave', onPressEnd);

    btn.addEventListener('touchstart', function(e) {
      e.preventDefault();
      onPressStart(e);
    }, { passive: false });

    btn.addEventListener('touchend', function(e) {
      e.preventDefault();
      onPressEnd(e);
    }, { passive: false });

    btn.addEventListener('touchcancel', onPressEnd);
  }

  function onPressStart(e) {
    if (isRecording) return;
    pressStartTime = Date.now();
    isLongPress = false;
    pressTimer = setTimeout(function() {
      isLongPress = true;
      startVoiceRecording();
    }, 500);
  }

  function onPressEnd(e) {
    clearTimeout(pressTimer);
    if (isRecording) return; // 录音中不打断

    if (!isLongPress && Date.now() - pressStartTime < 500) {
      App.DOM.chatInput.focus();
      Keyboard.show();
    }
  }

  function startVoiceRecording() {
    if (isRecording) return;
    isRecording = true;
    App.DOM.voiceBtn.classList.add('recording');

    App.appendChatMessage('agent', '🎤 正在聆听...');

    // 调用宿主机语音中继进行录音+识别
    fetch(RELAY_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ duration: 5 })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      isRecording = false;
      App.DOM.voiceBtn.classList.remove('recording');

      if (data.text) {
        App.DOM.chatInput.value = data.text;
        var text = data.text.trim();
        if (text) {
          App.sendUserMessage(text);
          App.DOM.chatInput.value = '';
        }
      } else if (data.error) {
        App.appendChatMessage('agent', '❌ 语音识别失败: ' + data.error);
      }
    })
    .catch(function(err) {
      isRecording = false;
      App.DOM.voiceBtn.classList.remove('recording');
      App.appendChatMessage('agent', '⚠️ 语音服务不可用，请检查 voice_relay.py 是否运行');
      console.error('Voice relay error:', err);
    });
  }

  return { init: init };
})();
