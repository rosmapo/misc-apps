// Beží v izolovanom svete rozšírenia (má prístup k chrome.runtime,
// ale nie priamo k window.WebSocket stránky - preto ho inject.js
// informuje cez postMessage).

window.addEventListener("message", (event) => {
  if (event.source !== window) return;
  const data = event.data;
  if (data && data.__simplenote_token_capture) {
    chrome.runtime.sendMessage({
      type: "SIMPLENOTE_TOKEN",
      token: data.token,
      appId: data.appId,
      capturedAt: Date.now(),
    });
  }
});
