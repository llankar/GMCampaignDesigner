const addressInput = document.getElementById("address-input");
const goButton = document.getElementById("go-button");
const importButton = document.getElementById("import-button");
const statusMessage = document.getElementById("status-message");

const status = {
  set(message, isError = false) {
    statusMessage.textContent = message;
    statusMessage.style.color = isError ? "#ff9b9b" : "";
  },
  clear() {
    statusMessage.textContent = "";
    statusMessage.style.color = "";
  },
};

const getTargetFromQuery = () => {
  const params = new URLSearchParams(window.location.search);
  return params.get("target") || "";
};

const resolveFrameUrl = () => {
  return window.location.href;
};

const navigateTo = (url) => {
  if (!url) {
    status.set("Adresse manquante.", true);
    return;
  }
  status.clear();
  window.location.assign(url);
  addressInput.value = url;
};

const sendSelection = async () => {
  const selection = window.getSelection()?.toString() ?? "";
  const trimmed = selection.trim();
  if (!trimmed) {
    status.set("Sélection vide.", true);
    return;
  }

  const currentUrl = resolveFrameUrl();
  if (window.pywebview?.api?.import_selection) {
    try {
      await window.pywebview.api.import_selection(trimmed, currentUrl);
      status.set("Sélection envoyée.");
    } catch (error) {
      status.set("Impossible d’envoyer la sélection.", true);
    }
  } else {
    status.set("API indisponible.", true);
  }
};

const initialTarget = getTargetFromQuery();
if (initialTarget) {
  navigateTo(initialTarget);
}

addressInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    navigateTo(addressInput.value.trim());
  }
});

goButton.addEventListener("click", () => {
  navigateTo(addressInput.value.trim());
});

importButton.addEventListener("click", () => {
  sendSelection();
});
