"use strict";

const svg = document.getElementById("graph");
const source = {value: ""};
const target = {value: ""};
const filter = document.getElementById("filter");
const page = document.getElementById("page");
const status = document.getElementById("status");
const colorMode = document.getElementById("color-mode");
const folderFilter = document.getElementById("folder-filter");
const fileFilter = document.getElementById("file-filter");
const relationFilter = document.getElementById("relation-filter");
const attributeFilter = document.getElementById("attribute-filter");
const attributeValue = document.getElementById("attribute-value");
const token = document.querySelector('meta[name="workspace-token"]').content;
const domain = new URLSearchParams(location.search).get("domain") || "";
const NS = "http://www.w3.org/2000/svg";
const colors = {
    "depends-on": "#ff786e", "part-of": "#72b7f2", "composed-of": "#7fce91",
    "implements": "#f5a64e", "extends": "#c89be5", "references": "#b7bfbe",
    "deprecates": "#d26678"
};
const width = 1100, height = 700, radius = 48;
let blocks = [], nodes = [], edges = [], dragged = null, moved = false, revision = "", detailId = "";
let positions = new Map();
const settingsKey = "wissenswiki.graph.v1." + (domain ? "domain." + domain : "wiki");
let savedSettings = {}, settingsError = "";
try {
    savedSettings = JSON.parse(localStorage.getItem(settingsKey) || "{}");
    if (!savedSettings || typeof savedSettings !== "object" || Array.isArray(savedSettings)) {
        throw new Error("Ungültiges Format");
    }
} catch (error) {
    settingsError = `Ansichtseinstellungen konnten nicht gelesen werden: ${error.message}`;
}
colorMode.value = savedSettings.color === "folder" ? "folder" : "uniform";
let hiddenAttributes = new Set(DEFAULT_HIDDEN_ATTRIBUTES);
try { hiddenAttributes = loadHiddenAttributes(domain); }
catch (error) {
    settingsError = [settingsError, `Attributeinstellungen konnten nicht gelesen werden: ${error.message}`]
        .filter(Boolean).join(" | ");
}
const settingsLink = document.getElementById("settings-link");
if (settingsLink) settingsLink.href = "/workspace/settings/" + location.search;
attributeValue.value = typeof savedSettings.value === "string" ? savedSettings.value : "";
svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

function saveSettings() {
    try {
        localStorage.setItem(settingsKey, JSON.stringify({
            color: colorMode.value, folder: folderFilter.value, file: fileFilter.value,
            relation: relationFilter.value,
            attribute: attributeFilter.value, value: attributeValue.value
        }));
    } catch (error) {
        status.textContent = `Ansichtseinstellungen konnten nicht gespeichert werden: ${error.message}`;
    }
}
function folderColor(folder) {
    let hash = 0;
    for (const char of folder) hash = (Math.imul(hash, 31) + char.codePointAt(0)) >>> 0;
    return `hsl(${hash % 360} 42% 34%)`;
}
function folderLabel(folder) { return folder === "." ? "(Wurzel)" : folder; }
// Die Beschriftung der "Alle"-Option kommt aus dem HTML der jeweiligen Ansicht.
function allOption(select) { return new Option(select.options[0]?.text || "Alle", ""); }
function populateFiles(file = fileFilter.value) {
    const files = new Set();
    for (const block of blocks) {
        if (folderFilter.value && block.attributes?.ordner === folderFilter.value && block.attributes?.datei) {
            files.add(block.attributes.datei);
        }
    }
    fileFilter.replaceChildren(allOption(fileFilter));
    for (const path of [...files].sort()) fileFilter.add(new Option(path.split("/").pop(), path));
    fileFilter.value = files.has(file) ? file : "";
    fileFilter.disabled = !folderFilter.value;
}
function populateSettings() {
    const folder = folderFilter.value || savedSettings.folder || "";
    const file = fileFilter.value || savedSettings.file || "";
    const folders = new Set(blocks.map(block => block.attributes?.ordner).filter(item => typeof item === "string"));
    folderFilter.replaceChildren(allOption(folderFilter));
    for (const item of [...folders].sort()) folderFilter.add(new Option(folderLabel(item), item));
    folderFilter.value = folders.has(folder) ? folder : "";
    folderFilter.disabled = !folders.size;
    populateFiles(file);
    const relation = relationFilter.value || savedSettings.relation || "";
    const attribute = attributeFilter.value || savedSettings.attribute || "";
    const types = new Set(), names = new Set();
    for (const block of blocks) {
        for (const item of block.relations) types.add(item.type);
        for (const key of Object.keys(flattenAttributes(block.attributes))) names.add(key);
    }
    relationFilter.replaceChildren(allOption(relationFilter));
    for (const type of [...types].sort()) relationFilter.add(new Option(type, type));
    relationFilter.value = types.has(relation) ? relation : "";
    attributeFilter.replaceChildren(allOption(attributeFilter));
    for (const name of [...names].sort()) attributeFilter.add(new Option(name, name));
    attributeFilter.value = names.has(attribute) ? attribute : "";
    attributeValue.disabled = !attributeFilter.value;
    savedSettings = {};
}
function updateFolderLegend(visible) {
    const legend = document.getElementById("folder-legend");
    if (!legend) return;
    legend.replaceChildren();
    if (colorMode.value !== "folder") return;
    const folders = [...new Set(visible.map(block => block.attributes?.ordner).filter(folder => folder !== undefined))].sort();
    if (!folders.length) { legend.textContent = "Keine Ordnerzuordnung vorhanden."; return; }
    for (const folder of folders) {
        const line = document.createElement("div");
        const swatch = element("svg", {class:"folder-swatch", viewBox:"0 0 10 10", "aria-hidden":"true"});
        swatch.append(element("circle", {cx:"5", cy:"5", r:"5", fill:folderColor(folder)}));
        line.append(swatch, document.createTextNode(folderLabel(folder)));
        legend.append(line);
    }
}
function nodeRadius(node) {
    return node.id === source.value || node.id === target.value ? radius * 1.5 : radius;
}
function element(name, attributes = {}) {
    const item = document.createElementNS(NS, name);
    for (const [key, value] of Object.entries(attributes)) item.setAttribute(key, value);
    return item;
}
function label(block, short = false) {
    const text = block.title.trim() || block.text.trim().replace(/\s+/g, " ").slice(0, 60) || block.id;
    const path = short && block.path ? block.path.split("/").pop() : block.path;
    return path ? `${text} (${path})${block.linkable ? "" : " – ohne stabile ID"}` : text;
}
const VOWEL = /[aeiouyäöüéèàáâ]/i;
const KEEP_TOGETHER = ["sch", "ch", "ck", "ph", "th", "qu"];
// Grobe Silbengrenzen: die neue Silbe beginnt mit einem Konsonanten (oder sch/ch/ck/ph/th/qu) vor einem Vokal.
function hyphenPoints(word) {
    const points = [];
    const lower = word.toLowerCase();
    for (let i = 2; i <= word.length - 2; i++) {
        if (!/\p{L}/u.test(word[i - 1]) || !/\p{L}/u.test(word[i]) || VOWEL.test(word[i])) continue;
        if (!VOWEL.test(word.slice(0, i))) continue;
        if (KEEP_TOGETHER.some(group => {
            const start = lower.indexOf(group, Math.max(0, i - group.length + 1));
            return start >= 0 && start < i && start + group.length > i;
        })) continue;
        const onset = KEEP_TOGETHER.find(group => lower.startsWith(group, i)) || lower[i];
        if (VOWEL.test(lower[i + onset.length] || "")) points.push(i);
    }
    return points;
}
function splitWord(word, room) {
    if (/[-/_.]/.test(word.slice(1, room))) {
        const cut = Math.max(...[..."-/_."].map(mark => word.lastIndexOf(mark, room - 1)));
        if (cut > 0) return [word.slice(0, cut + 1), word.slice(cut + 1)];
    }
    const points = hyphenPoints(word).filter(point => point + 1 <= room);
    if (!points.length) return null;
    const point = points[points.length - 1];
    return [word.slice(0, point) + "-", word.slice(point)];
}
function bubbleLines(title, width = 14, maxLines = 3) {
    const words = title.split(/\s+/).filter(Boolean);
    const lines = [];
    let line = "";
    while (words.length && lines.length < maxLines) {
        const word = words[0];
        const candidate = line ? `${line} ${word}` : word;
        if (candidate.length <= width) { line = candidate; words.shift(); continue; }
        const room = width - (line ? line.length + 1 : 0);
        const parts = room >= 3 ? splitWord(word, room) : null;
        if (parts) {
            line = line ? `${line} ${parts[0]}` : parts[0];
            words[0] = parts[1];
        } else if (!line) {
            line = word.slice(0, width - 1) + "-";
            words[0] = word.slice(width - 1);
        }
        lines.push(line);
        line = "";
    }
    if (line && lines.length < maxLines) lines.push(line);
    if (words.length) {
        const last = lines[lines.length - 1].replace(/-$/, "");
        lines[lines.length - 1] = (last.length >= width ? last.slice(0, width - 1) : last) + "…";
    }
    return lines;
}
function showBlock(id) {
    detailId = id;
    const block = blocks.find(item => item.id === id);
    const details = document.getElementById("detail-attributes");
    if (!details) return;
    details.replaceChildren();
    if (block) {
        for (const [name, value] of Object.entries(flattenAttributes(block.attributes))) {
            const term = document.createElement("dt"), description = document.createElement("dd");
            term.textContent = name; description.textContent = value;
            details.append(term, description);
        }
    }
}
function showComparison(table) {
    const selected = [source.value, target.value].map(id => blocks.find(block => block.id === id));
    const values = selected.map(block => block ? flattenAttributes(block.attributes) : {});
    const names = [...new Set(values.flatMap(item => Object.keys(item)))]
        .filter(name => !hiddenAttributes.has(attributeShortName(name)));
    const cell = (className, text, title = text) => {
        const item = document.createElement("div");
        item.className = className; item.textContent = text; item.title = title;
        return item;
    };
    table.replaceChildren(cell("compare-head", ""),
        cell("compare-head source-column", selected[0] ? label(selected[0]) : "Ausgang: nicht gewählt"),
        cell("compare-head target-column", selected[1] ? label(selected[1]) : "Ziel: nicht gewählt"));
    for (const name of names) {
        table.append(cell("compare-name", attributeShortName(name), name),
            cell("compare-value source-column", values[0][name] ?? ""),
            cell("compare-value target-column", values[1][name] ?? ""));
    }
}
function reflectSelection() {
    const comparison = document.getElementById("attribute-compare");
    if (comparison) showComparison(comparison);
    for (const [name, selection] of [["source", source], ["target", target]]) {
        const selected = blocks.find(block => block.id === selection.value);
        document.getElementById(name + "-label").textContent = selected ? label(selected) : "Nicht gewählt";
    }
    for (const node of nodes) {
        node.group.classList.toggle("source", node.id === source.value);
        node.group.classList.toggle("target", node.id === target.value);
        node.group.querySelector("circle").setAttribute("r", nodeRadius(node));
    }
}
function selectNode(id) {
    if (!source.value || (source.value && target.value)) {
        source.value = id;
        target.value = "";
    } else if (source.value !== id) {
        target.value = id;
    }
    showBlock(id);
    reflectSelection();
}
function point(event) {
    const matrix = svg.getScreenCTM();
    return new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
}
function clamp(value, min, max) { return Math.min(max, Math.max(min, value)); }

function build() {
    if (!blocks.some(block => block.id === source.value)) source.value = "";
    if (!blocks.some(block => block.id === target.value)) target.value = "";
    svg.replaceChildren();
    const defs = element("defs");
    const marker = element("marker", {id:"arrow", viewBox:"0 0 10 10", refX:"9", refY:"5",
        markerWidth:"7", markerHeight:"7", orient:"auto-start-reverse"});
    marker.append(element("path", {d:"M 0 0 L 10 5 L 0 10 z", fill:"context-stroke"}));
    defs.append(marker); svg.append(defs);
    const edgeLayer = element("g"), nodeLayer = element("g");
    svg.append(edgeLayer, nodeLayer);
    const query = filter.value.trim().toLocaleLowerCase();
    const attributeQuery = attributeValue.value.trim().toLocaleLowerCase();
    let matches = blocks.filter(block => {
        if (!(label(block) + "\n" + block.text).toLocaleLowerCase().includes(query)) return false;
        if (folderFilter.value && block.attributes?.ordner !== folderFilter.value) return false;
        if (fileFilter.value && block.attributes?.datei !== fileFilter.value) return false;
        const attributes = flattenAttributes(block.attributes);
        if (attributeFilter.value && (!(attributeFilter.value in attributes) ||
            !attributes[attributeFilter.value].toLocaleLowerCase().includes(attributeQuery))) return false;
        return true;
    });
    if (relationFilter.value) {
        const ids = new Set(matches.map(block => block.id)), related = new Set();
        for (const block of matches) for (const relation of block.relations) {
            if (relation.type === relationFilter.value && ids.has(relation.target)) {
                related.add(block.id); related.add(relation.target);
            }
        }
        matches = matches.filter(block => related.has(block.id));
    }
    const matchingIds = new Set(matches.map(block => block.id));
    if (source.value && !matchingIds.has(source.value)) source.value = "";
    if (target.value && !matchingIds.has(target.value)) target.value = "";
    if (!source.value && target.value) { source.value = target.value; target.value = ""; }
    if (detailId && !matchingIds.has(detailId)) showBlock("");
    const totalPages = Math.max(1, Math.ceil(matches.length / 60));
    const pageIndex = Math.min(Number(page.value) || 0, totalPages - 1);
    page.replaceChildren();
    for (let i = 0; i < totalPages; i++) page.add(new Option(`${i + 1} / ${totalPages}`, String(i)));
    page.value = String(pageIndex);
    const visible = matches.slice(pageIndex * 60, (pageIndex + 1) * 60);
    for (const id of [source.value, target.value]) {
        const selected = blocks.find(block => block.id === id);
        if (selected && !visible.includes(selected)) visible.push(selected);
    }
    updateFolderLegend(visible);
    const count = document.getElementById("count");
    count.textContent = count.dataset.format === "short" ? `${matches.length}/${blocks.length}`
        : `${matches.length} Treffer · ${blocks.length} insgesamt`;
    nodes = visible.map((block, index) => {
        const previous = positions.get(block.id);
        const angle = index * 2.399963;
        const distance = Math.min(290, 95 + Math.sqrt(index) * 55);
        const node = {id:block.id, x:previous?.x ?? width / 2 + Math.cos(angle) * distance,
            y:previous?.y ?? height / 2 + Math.sin(angle) * distance, vx:0, vy:0};
        const group = element("g", {class:"node", tabindex:"0", role:"button",
            "aria-label":`Block ${label(block)} auswählen`});
        const folder = block.attributes?.ordner;
        const fill = colorMode.value === "folder" && folder !== undefined ? folderColor(folder) : "#294b49";
        group.append(element("circle", {r:radius, fill}));
        const text = element("text", {});
        const lines = bubbleLines(label(block, true));
        lines.forEach((line, index) => {
            const span = element("tspan", {x:"0", dy: index ? "1.15em" : `${0.35 - (lines.length - 1) * 0.575}em`});
            span.textContent = line;
            text.append(span);
        });
        group.append(text);
        group.addEventListener("pointerdown", event => {
            if (event.button !== 0) return;
            dragged = node; moved = false; group.setPointerCapture(event.pointerId);
        });
        group.addEventListener("pointermove", event => {
            if (dragged !== node) return;
            const p = point(event);
            if (Math.hypot(p.x - node.x, p.y - node.y) > 2) moved = true;
            if (moved) {
                const r = nodeRadius(node);
                node.x = clamp(p.x, r, width - r); node.y = clamp(p.y, r, height - r);
            }
        });
        group.addEventListener("pointerup", () => {
            if (dragged === node && !moved) selectNode(node.id);
            dragged = null;
        });
        group.addEventListener("pointercancel", () => { dragged = null; });
        group.addEventListener("keydown", event => {
            if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectNode(node.id); }
        });
        node.group = group; nodeLayer.append(group); return node;
    });
    const lookup = new Map(nodes.map(node => [node.id, node]));
    const unresolved = document.getElementById("unresolved");
    unresolved.replaceChildren();
    edges = [];
    const allIds = new Set(blocks.map(block => block.id));
    for (const block of visible) {
        for (const relation of block.relations) {
            if (relationFilter.value && relation.type !== relationFilter.value) continue;
            const from = lookup.get(block.id), to = lookup.get(relation.target);
            if (!to && !allIds.has(relation.target)) {
                const li = document.createElement("li");
                li.textContent = `${label(block)} → ${relation.target}: Ziel nicht gefunden (${relation.type})`;
                unresolved.append(li); continue;
            }
            if (!to) continue;
            const color = colors[relation.type] || "#777";
            const path = element("path", {class:"edge", stroke:color, "marker-end":"url(#arrow)"});
            const text = element("text", {class:"edge-label", fill:color});
            text.textContent = relation.type;
            edgeLayer.append(path, text);
            edges.push({from, to, path, text});
        }
    }
    document.getElementById("empty").textContent = nodes.length ? "" : "Keine passenden Blöcke.";
    positions = lookup;
    reflectSelection();
}

function animate() {
    for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
            const b = nodes[j];
            let dx = a.x - b.x, dy = a.y - b.y;
            if (Math.abs(dx) + Math.abs(dy) < 0.1) dx = 0.1;
            const dist2 = Math.max(100, dx * dx + dy * dy), dist = Math.sqrt(dist2);
            const overlap = Math.max(0, nodeRadius(a) + nodeRadius(b) + 10 - dist);
            const force = Math.min(2.5, 3000 / dist2 + overlap * 0.02);
            a.vx += dx / dist * force; a.vy += dy / dist * force;
            b.vx -= dx / dist * force; b.vy -= dy / dist * force;
        }
    }
    for (const edge of edges) {
        const dx = edge.to.x - edge.from.x, dy = edge.to.y - edge.from.y;
        const distance = Math.max(1, Math.hypot(dx, dy));
        const force = (distance - 220) * 0.0015;
        edge.from.vx += dx / distance * force; edge.from.vy += dy / distance * force;
        edge.to.vx -= dx / distance * force; edge.to.vy -= dy / distance * force;
    }
    for (const node of nodes) {
        node.vx = (node.vx + (width / 2 - node.x) * .0007) * .93;
        node.vy = (node.vy + (height / 2 - node.y) * .0007) * .93;
        if (node !== dragged) {
            const r = nodeRadius(node);
            node.x = clamp(node.x + node.vx, r, width - r);
            node.y = clamp(node.y + node.vy, r, height - r);
        } else { node.vx = 0; node.vy = 0; }
        node.group.setAttribute("transform", `translate(${node.x} ${node.y})`);
    }
    for (const edge of edges) {
        const dx = edge.to.x - edge.from.x, dy = edge.to.y - edge.from.y;
        const distance = Math.max(1, Math.hypot(dx, dy));
        const fromRadius = nodeRadius(edge.from), toRadius = nodeRadius(edge.to) + 2;
        const x1 = edge.from.x + dx / distance * fromRadius, y1 = edge.from.y + dy / distance * fromRadius;
        const x2 = edge.to.x - dx / distance * toRadius, y2 = edge.to.y - dy / distance * toRadius;
        const mx = (x1 + x2) / 2 - dy / distance * 24, my = (y1 + y2) / 2 + dx / distance * 24;
        edge.path.setAttribute("d", `M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`);
        edge.text.setAttribute("x", (x1 + 2 * mx + x2) / 4);
        edge.text.setAttribute("y", (y1 + 2 * my + y2) / 4 - 3);
    }
    requestAnimationFrame(animate);
}
async function load() {
    const response = await fetch("/workspace/api" + (domain ? "?domain=" + encodeURIComponent(domain) : ""));
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Blöcke konnten nicht geladen werden.");
    blocks = result.blocks;
    revision = result.revision || "";
    populateSettings();
    build();
    const warnings = result.errors || [];
    status.textContent = [settingsError, warnings.length ? `${warnings.length} Hinweise: ${warnings.join(" | ")}` : ""]
        .filter(Boolean).join(" | ");
}
async function action(callback) {
    try { status.textContent = ""; await callback(); }
    catch (error) { status.textContent = error.message; }
}
document.getElementById("reload").addEventListener("click", () => action(load));
document.getElementById("clear").addEventListener("click", () => {
    source.value = ""; target.value = ""; showBlock(""); reflectSelection();
});
filter.addEventListener("input", () => { page.value = "0"; build(); });
page.addEventListener("change", build);
folderFilter.addEventListener("change", () => { populateFiles(""); page.value = "0"; build(); saveSettings(); });
fileFilter.addEventListener("change", () => { page.value = "0"; build(); saveSettings(); });
for (const control of [colorMode, relationFilter, attributeFilter, attributeValue]) {
    control.addEventListener(control === attributeValue ? "input" : "change", () => {
        attributeValue.disabled = !attributeFilter.value;
        page.value = "0"; build(); saveSettings();
    });
}
document.getElementById("reset-settings").addEventListener("click", () => {
    colorMode.value = "uniform"; folderFilter.value = ""; populateFiles("");
    relationFilter.value = ""; attributeFilter.value = "";
    attributeValue.value = ""; attributeValue.disabled = true;
    filter.value = ""; page.value = "0"; build(); saveSettings();
});
document.getElementById("connect").addEventListener("click", () => action(async () => {
    const block = blocks.find(item => item.id === source.value);
    if (!block || !target.value || source.value === target.value) {
        throw new Error("Bitte zwei verschiedene Blöcke auswählen.");
    }
    const response = await fetch("/workspace/api", {method:"POST",
        headers:{"Content-Type":"application/json", "X-Workspace-Token":token},
        body:JSON.stringify({action:"graph-relate", id:block.id, revision:domain ? revision : block.revision,
            target:target.value, type:document.querySelector('input[name="relation-type"]:checked').value, domain})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Beziehung konnte nicht gespeichert werden.");
    await load();
    status.textContent = "Beziehung gespeichert.";
}));
action(load);
requestAnimationFrame(animate);
