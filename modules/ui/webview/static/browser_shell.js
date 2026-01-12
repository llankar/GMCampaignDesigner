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

const waitForApi = () =>
  new Promise((resolve) => {
    if (window.pywebview?.api) {
      resolve();
      return;
    }
    window.addEventListener("pywebviewready", () => resolve(), { once: true });
  });

const setInitialTarget = async () => {
  await waitForApi();
  if (!window.pywebview?.api?.get_initial_target) {
    return;
  }
  try {
    const target = await window.pywebview.api.get_initial_target();
    if (target) {
      addressInput.value = target;
    }
  } catch (error) {
    status.set("Unable to read initial address.", true);
  }
};

const navigateTo = async (url) => {
  if (!url) {
    status.set("Missing address.", true);
    return;
  }
  await waitForApi();
  if (!window.pywebview?.api?.navigate) {
    status.set("API unavailable.", true);
    return;
  }
  status.clear();
  try {
    const response = await window.pywebview.api.navigate(url);
    addressInput.value = url;
    if (response?.ok === false) {
      status.set(response.message || "Unable to open address.", true);
    }
  } catch (error) {
    status.set("Unable to open address.", true);
  }
};

const sendSelection = async () => {
  await waitForApi();
  if (!window.pywebview?.api?.import_selection) {
    status.set("API unavailable.", true);
    return;
  }
  try {
    const response = await window.pywebview.api.import_selection();
    if (response?.ok) {
      status.set(response.message || "Selection sent.");
    } else {
      status.set(response?.message || "Unable to send selection.", true);
    }
  } catch (error) {
    status.set("Unable to send selection.", true);
  }
};

setInitialTarget();

addressInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    void navigateTo(addressInput.value.trim());
  }
});

goButton.addEventListener("click", () => {
  void navigateTo(addressInput.value.trim());
});

importButton.addEventListener("click", () => {
  void sendSelection();
});
