const tokenBox = document.getElementById("tokenBox");
const metaDiv = document.getElementById("meta");
const toggleBtn = document.getElementById("toggleBtn");
const copyBtn = document.getElementById("copyBtn");

let currentToken = null;
let visible = false;

function mask(token) {
  if (token.length <= 10) return "•".repeat(token.length);
  return token.slice(0, 6) + "…" + token.slice(-4);
}

function render() {
  if (!currentToken) {
    tokenBox.textContent = "Zatiaľ nič nezachytené. Otvor/obnov app.simplenote.com a prihlás sa.";
    tokenBox.classList.add("empty");
    toggleBtn.disabled = true;
    copyBtn.disabled = true;
    return;
  }
  tokenBox.classList.remove("empty");
  tokenBox.textContent = visible ? currentToken : mask(currentToken);
  toggleBtn.disabled = false;
  copyBtn.disabled = false;
  toggleBtn.textContent = visible ? "Skryť" : "Zobraziť";
}

function loadFromStorage() {
  chrome.storage.local.get(["simplenoteToken", "capturedAt"], (result) => {
    currentToken = result.simplenoteToken || null;
    if (result.capturedAt) {
      const date = new Date(result.capturedAt);
      metaDiv.textContent = "Zachytené: " + date.toLocaleString("sk-SK");
    } else {
      metaDiv.textContent = "";
    }
    render();
  });
}

toggleBtn.addEventListener("click", () => {
  visible = !visible;
  render();
});

copyBtn.addEventListener("click", () => {
  if (!currentToken) return;
  navigator.clipboard.writeText(currentToken).then(() => {
    copyBtn.textContent = "Skopírované!";
    setTimeout(() => (copyBtn.textContent = "Kopírovať"), 1500);
  });
});

// automaticky sa obnoví, ak sa token zachytí kým je popup otvorený
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.simplenoteToken) {
    loadFromStorage();
  }
});

loadFromStorage();
