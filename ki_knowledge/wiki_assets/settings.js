"use strict";

const domain = new URLSearchParams(location.search).get("domain") || "";
const status = document.getElementById("status");
const options = document.getElementById("attribute-options");
let names = new Map();

document.getElementById("back-link").href = "/workspace/graph-header/" + location.search;

function render(hidden) {
    options.replaceChildren();
    for (const [name, fullNames] of [...names].sort(([a], [b]) => a.localeCompare(b))) {
        const label = document.createElement("label");
        const box = document.createElement("input");
        box.type = "checkbox"; box.value = name; box.checked = !hidden.has(name);
        label.title = [...fullNames].sort().join("\n");
        label.append(box, " " + name);
        options.append(label);
    }
}
function save() {
    const hidden = new Set([...options.querySelectorAll("input")].filter(box => !box.checked).map(box => box.value));
    try {
        saveHiddenAttributes(domain, hidden);
        status.textContent = "Gespeichert.";
    } catch (error) {
        status.textContent = `Einstellungen konnten nicht gespeichert werden: ${error.message}`;
    }
}
async function load() {
    const response = await fetch("/workspace/api" + (domain ? "?domain=" + encodeURIComponent(domain) : ""));
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Blöcke konnten nicht geladen werden.");
    names = new Map();
    for (const block of result.blocks) {
        for (const name of Object.keys(flattenAttributes(block.attributes))) {
            const short = attributeShortName(name);
            if (!names.has(short)) names.set(short, new Set());
            names.get(short).add(name);
        }
    }
    let hidden;
    try { hidden = loadHiddenAttributes(domain); }
    catch (error) {
        hidden = new Set(DEFAULT_HIDDEN_ATTRIBUTES);
        status.textContent = `Gespeicherte Einstellungen nicht lesbar, Standard angezeigt: ${error.message}`;
    }
    render(hidden);
    if (!names.size) status.textContent = "Keine Attribute vorhanden.";
}
options.addEventListener("change", save);
document.getElementById("show-all").addEventListener("click", () => { render(new Set()); save(); });
document.getElementById("show-none").addEventListener("click", () => { render(new Set(names.keys())); save(); });
document.getElementById("show-default").addEventListener("click", () => {
    render(new Set(DEFAULT_HIDDEN_ATTRIBUTES)); save();
});
load().catch(error => { status.textContent = error.message; });
