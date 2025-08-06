(async () => {
    let jsonData = null;
    // Default fallback relative path for portrait images (without a "data/" prefix)
    let derivedPortraitBase = "images/DresdenFiles/Scenarios/portrait";

    // --- STEP 1: Prompt the user to select a local JSON file using a native file input ---
    await new Promise((resolve, reject) => {
        new Dialog({
            title: "Select Local JSON File",
            content: `
        <p>Select the JSON file you want to load from your local disk:</p>
        <input type="file" id="jsonFile" accept=".json" style="width:100%;" webkitdirectory />
      `,
            buttons: {
                load: {
                    label: "Load",
                    callback: (html) => {
                        const fileInput = html.find("#jsonFile")[0];
                        if (!fileInput.files.length) {
                            ui.notifications.error("No file selected!");
                            reject(new Error("No file selected"));
                            return;
                        }
                        const file = fileInput.files[0];
                        // Try to derive the relative portrait base directory from the file's full path.
                        const fullPath = file.path || file.webkitRelativePath || "";
                        if (fullPath) {
                            let normalized = fullPath.replace(/\\/g, "/");
                            let lower = normalized.toLowerCase();
                            let idx = lower.indexOf("/data/");
                            if (idx !== -1) {
                                let relativePath = normalized.substring(idx + 1); // e.g., "data/..."
                                let lastSlash = relativePath.lastIndexOf("/");
                                if (lastSlash !== -1) {
                                    derivedPortraitBase = relativePath.substring(0, lastSlash) + "/portraits";
                                }
                            } else {
                                let lastSlash = normalized.lastIndexOf("/");
                                if (lastSlash !== -1) {
                                    derivedPortraitBase = normalized.substring(0, lastSlash) + "/portraits";
                                }
                            }
                            // Remove a leading "data/" if present.
                            if (derivedPortraitBase.toLowerCase().startsWith("data/")) {
                                derivedPortraitBase = derivedPortraitBase.substring(5);
                                if (derivedPortraitBase.startsWith("/")) {
                                    derivedPortraitBase = derivedPortraitBase.substring(1);
                                }
                            }
                        }
                        console.log("Derived portrait base:", derivedPortraitBase);
                        const reader = new FileReader();
                        reader.onload = (evt) => {
                            try {
                                jsonData = JSON.parse(evt.target.result);
                                resolve();
                            } catch (err) {
                                ui.notifications.error("Failed to parse JSON file!");
                                reject(err);
                            }
                        };
                        reader.readAsText(file);
                    }
                },
                cancel: {
                    label: "Cancel",
                    callback: () => reject(new Error("User cancelled file selection"))
                }
            },
            default: "load"
        }).render(true);
    }).catch(err => {
        ui.notifications.error(err);
    });
    if (!jsonData) return;

    console.log("Loaded JSON data:", jsonData);
    console.log("Final derived portrait directory:", derivedPortraitBase);

    // --- STEP 2: Create (or find) the folders for Scenarios, Places, and NPCs ---
    let scenarioFolder = game.folders.find(f => f.name === "Scenarios" && f.type === "Scene");
    if (!scenarioFolder) {
        scenarioFolder = await Folder.create({ name: "Scenarios", type: "Scene", parent: null });
    }
    let placesFolder = game.folders.find(f => f.name === "Places" && f.type === "Scene");
    if (!placesFolder) {
        placesFolder = await Folder.create({ name: "Places", type: "Scene", parent: null });
    }
    let npcFolder = game.folders.find(f => f.name === "NPCs" && f.type === "Actor");
    if (!npcFolder) {
        npcFolder = await Folder.create({ name: "NPCs", type: "Actor", parent: null });
    }

    // --- STEP 3: Basic scene settings ---
    const sceneWidth = 1920;
    const sceneHeight = 1080;
    const gridSize = 100;
    const defaultSceneImg = "icons/svg/scene.svg"; // fallback background image

    // --- STEP 4: Dictionary to avoid duplicate Actors ---
    let actorsByName = {};

    /**
     * Helper function to create (or reuse) an Actor for an NPC token.
     * The portrait path is rebuilt using the derived portrait base directory.
     */
    async function getOrCreateActor(t) {
        if (actorsByName[t.name]) return actorsByName[t.name];

        const combinedDescription = `
<b>Role:</b> ${t.role || "—"}
<br><b>Description:</b> ${t.description || "—"}
<br><b>Secrets:</b> ${t.secrets || "—"}
    `.trim();

        let portrait = t.portrait || "";
        if (portrait) {
            portrait = portrait.replace("\\", "/");
            let fileName = portrait.split("/").pop();
            portrait = `${derivedPortraitBase}/${fileName}`;
        } else {
            portrait = "icons/svg/mystery-man.svg";
        }

        const actorData = {
            name: t.name,
            type: "npc",
            img: portrait,
            folder: npcFolder.id,
            system: {
                details: {
                    biography: { value: combinedDescription }
                }
            },
            flags: {
                GMCampaignDesigner: {
                    factions: t.factions || [],
                    borderColor: t.borderColor || "#000000"
                }
            }
        };

        const actor = await Actor.create(actorData, { noHook: true });
        actorsByName[t.name] = actor.id;
        return actor.id;
    }

    // Helper: use actor's actual token image (using prototypeToken.texture.src if available)
    function getTokenImage(actorId) {
        const actor = game.actors.get(actorId);
        if (!actor) return "icons/svg/mystery-man.svg";
        const proto = actor.prototypeToken;
        if (proto && proto.texture && proto.texture.src) return proto.texture.src;
        return actor.img || "icons/svg/mystery-man.svg";
    }

    // Helper: convert HTML to plain text for the drawing text box
    function htmlToPlainText(html) {
        return html
            .replace(/<br\s*\/?>/gi, "\n")
            .replace(/<\/p>/gi, "\n\n")
            .replace(/<[^>]+>/g, "")
            .trim();
    }

    // --- STEP 5: Process each scenario and build scenes ---
    if (Array.isArray(jsonData.scenes)) {
        for (let scenario of jsonData.scenes) {
            let sceneTitle = scenario.title || scenario.Title || "Untitled Scenario";
            let sceneSummary = scenario.summary || scenario.Summary || "";
            let sceneSecrets = scenario.secrets || scenario.Secrets || "";

            // Build tokens array
            let tokens = [];
            let scenarioTokens = scenario.tokens || scenario.Tokens || [];
            let startX = 300;          // Where the first token is placed
            let startY = 730;          // Vertical position for all tokens
            let offsetX = 120;         // Horizontal spacing between tokens

            for (let [idx, t] of scenarioTokens.entries()) {
                const actorId = await getOrCreateActor(t);
                const finalTokenImg = getTokenImage(actorId);

                // Each token is offset horizontally by idx * offsetX
                tokens.push({
                    actorId: actorId,
                    x: startX + (idx * offsetX),
                    y: startY,
                    width: 1,
                    height: 1,
                    name: t.name || "",
                    actorLink: true,
                    hidden: false,
                    texture: { src: finalTokenImg }
                });
            }

            // Build scene description (HTML) and convert to plain text for drawing
            let sceneHTML = `<p>${sceneSummary}</p>`;
            if (sceneSecrets.trim() !== "") {
                sceneHTML += `<h2>Secrets : </h2><p>${sceneSecrets}</p>`;
            }
            let plainText = htmlToPlainText(sceneHTML);

            let createdScene = await Scene.create({
                name: sceneTitle,
                img: defaultSceneImg,
                width: sceneWidth,
                height: sceneHeight,
                grid: gridSize,
                navigation: true,
                padding: 0.0,
                description: sceneHTML,
                tokens: tokens,
                folder: scenarioFolder.id,
                backgroundColor: "#222222",

                // Set the initial camera view
                initial: {
                    x: 1071,          // the X coordinate of the camera’s center
                    y: 552,           // the Y coordinate of the camera’s center
                    scale: 0.84       // zoom level, e.g. 0.84
                }
            });

            // Delay briefly to allow the scene to render its container before adding tiles.
            await new Promise(resolve => setTimeout(resolve, 500));
            let scenarioMarkers = scenario.markers || scenario.Markers || [];
            if (Array.isArray(scenarioMarkers) && scenarioMarkers.length > 0) {
                let tileData = [];
                for (let m of scenarioMarkers) {
                    tileData.push({
                        img: m.icon || "icons/svg/anchor.svg",
                        x: m.x ?? 0,
                        y: m.y ?? 0,
                        width: 64,
                        height: 64,
                        alpha: 1.0,
                        locked: false,
                        flags: {
                            GMCampaignDesigner: {
                                targetScene: m.targetScene || "",
                                name: m.name || "",
                                description: m.description || ""
                            }
                        }
                    });
                }
                try {
                    await createdScene.createEmbeddedDocuments("Tile", tileData);
                } catch (err) {
                    console.error("Error creating Tiles:", err);
                    ui.notifications.error("Failed to create markers for scene " + sceneTitle);
                }
            }

            // Create a text drawing for the scene description on the canvas
            try {
                await createdScene.createEmbeddedDocuments("Drawing", [{
                    type: "t",
                    text: plainText,
                    shape: { "type": "r", "width": 600, "height": 300, "radius": null, "points": [] },
                    x: 660,       // center horizontally for a 1920 width scene
                    y: 400,       // center vertically for a 1080 height scene
                    scale: 1,
                    fillColor: "#ffffff",
                    fillAlpha: 1,
                    fillType: 1,
                    strokeColor: "#000000",
                    strokeAlpha: 1,
                    strokeWidth: 2,
                    textColor: "#000000",
                    textAlpha: 1,
                    fontSize: 24,
                    textAlign: "center"
                }]);
            } catch (err) {
                console.error("Error creating text drawing:", err);
                ui.notifications.error("Failed to create text drawing for scene " + sceneTitle);
            }
        }
    }

    // --- STEP 6: Process Places -> separate Scenes ---
    if (Array.isArray(jsonData.places)) {
        for (let p of jsonData.places) {
            let placeTitle = p.title || p.Title || "Unnamed Place";
            let placeDescription = p.description || p.Description || "";
            let placeImage = p.image || p.Image || defaultSceneImg;
            await Scene.create({
                name: placeTitle,
                img: placeImage,
                width: sceneWidth,
                height: sceneHeight,
                grid: gridSize,
                navigation: true,
                padding: 0.25,
                description: `<p>${placeDescription}</p>`,
                folder: placesFolder.id,
                backgroundColor: "#222222"
            });
        }
    }

    ui.notifications.info("Import complete! Scenes and Actors created in their respective folders.");
})();