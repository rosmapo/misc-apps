chrome.runtime.onMessage.addListener((message) => {
  if (message && message.type === "SIMPLENOTE_TOKEN") {
    chrome.storage.local.set({
      simplenoteToken: message.token,
      simplenoteAppId: message.appId,
      capturedAt: message.capturedAt,
    });
    chrome.action.setBadgeText({ text: "OK" });
    chrome.action.setBadgeBackgroundColor({ color: "#4CAF50" });
  }
});
