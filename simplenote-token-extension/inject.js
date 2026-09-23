// Beží priamo v kontexte stránky app.simplenote.com (world: "MAIN"),
// aby mal prístup k tomu istému window.WebSocket, ktorý appka reálne používa.
// "Podčapne" WebSocket.send() a keď zachytí init správu s tokenom,
// pošle ju cez window.postMessage do content.js (izolovaný svet rozšírenia).

(function () {
  const OriginalWebSocket = window.WebSocket;

  function PatchedWebSocket(url, protocols) {
    const ws = protocols !== undefined
      ? new OriginalWebSocket(url, protocols)
      : new OriginalWebSocket(url);

    const originalSend = ws.send.bind(ws);

    ws.send = function (data) {
      try {
        if (typeof data === "string" && data.includes('"token"') && data.includes('"app_id"')) {
          const tokenMatch = data.match(/"token"\s*:\s*"([^"]+)"/);
          const appIdMatch = data.match(/"app_id"\s*:\s*"([^"]+)"/);
          if (tokenMatch) {
            window.postMessage(
              {
                __simplenote_token_capture: true,
                token: tokenMatch[1],
                appId: appIdMatch ? appIdMatch[1] : null,
              },
              "*"
            );
          }
        }
      } catch (e) {
        // ticho ignorovať - nechceme appke rozbiť normálnu funkčnosť
      }
      return originalSend(data);
    };

    return ws;
  }

  PatchedWebSocket.prototype = OriginalWebSocket.prototype;
  window.WebSocket = PatchedWebSocket;
})();
