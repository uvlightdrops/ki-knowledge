"use strict";
const token = document.querySelector('meta[name="workspace-token"]').content;
let blocks = [];
const state = {left: {id: "", revision: "", dirty: false}, right: {id: "", revision: "", dirty: false}};
const status = document.getElementById("status");
function message(text) { status.textContent = text; }
function panel(side) { return document.getElementById(side); }
function element(side, name) { return panel(side).querySelector("." + name); }
function find(id) { return blocks.find(block => block.id === id); }
function label(block) { return block ? (block.title.trim() || block.text.trim().slice(0, 60) || block.id) : "Nicht gefunden"; }
async function request(action, payload = {}) {
    const response = await fetch("/workspace/api", {method:"POST",
        headers:{"Content-Type":"application/json", "X-Workspace-Token":token},
        body:JSON.stringify({action,...payload})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Anfrage fehlgeschlagen.");
    return result;
}
async function refresh() {
    const response = await fetch("/workspace/api");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Arbeitsraum konnte nicht geladen werden.");
    blocks = result.blocks;
    renderBrowser();
}
function button(text, fn) {
    const result = document.createElement("button");
    result.textContent = text;
    result.addEventListener("click", fn);
    return result;
}
function openBlock(side, id) {
    if (state[side].id === id) return;
    if (state[side].dirty && !confirm("Ungespeicherte Änderungen verwerfen?")) {
        element(side, "select").value = state[side].id;
        return;
    }
    state[side] = {id, revision:"", dirty:false};
    render(side);
}
function renderBrowser() {
    const list = document.getElementById("block-list");
    const query = document.getElementById("block-search").value.trim().toLocaleLowerCase();
    const matches = blocks.filter(block =>
        (block.title + "\n" + block.text + "\n" + block.id).toLocaleLowerCase().includes(query));
    list.replaceChildren();
    for (const block of matches) {
        const li = document.createElement("li");
        li.append(button(label(block), () => openBlock(
            document.querySelector('input[name="open-side"]:checked').value, block.id)));
        list.append(li);
    }
    document.getElementById("block-list-empty").textContent =
        matches.length ? "" : (blocks.length ? "Keine passenden Blöcke." : "Noch keine Blöcke.");
}
function render(side) {
    const current = state[side], select = element(side, "select");
    select.replaceChildren();
    const empty = document.createElement("option"); empty.value = ""; empty.textContent = "Neuer Block";
    select.append(empty);
    for (const block of blocks) {
        const option = document.createElement("option");
        option.value = block.id; option.textContent = label(block); select.append(option);
    }
    select.value = current.id;
    const block = find(current.id);
    current.revision = block?.revision || "";
    element(side, "title").value = block?.title || "";
    element(side, "text").value = block?.text || "";
    element(side, "identity").textContent = block ? "ID: " + block.id : "Noch nicht gespeichert";
    const relations = element(side, "relations"); relations.replaceChildren();
    const parts = element(side, "parts"); parts.replaceChildren();
    const preview = element(side, "preview"); preview.textContent = "";
    if (!block) return;
    block.relations.forEach((relation, index) => {
        const li = document.createElement("li");
        li.append(document.createTextNode(relation.type + " → "));
        const target = find(relation.target);
        if (target) li.append(button(label(target), () => openBlock(side === "left" ? "right" : "left", target.id)));
        else li.append(document.createTextNode("Nicht gefunden (" + relation.target + ")"));
        li.append(button("Entfernen", () => removeRelation(side, index)));
        relations.append(li);
    });
    block.parts.forEach((id, index) => {
        const li = document.createElement("li");
        li.append(document.createTextNode(label(find(id)) + (!find(id) ? " (" + id + ")" : "")));
        if (index > 0) li.append(button("↑", () => changeParts(side, index, -1)));
        if (index < block.parts.length - 1) li.append(button("↓", () => changeParts(side, index, 1)));
        li.append(button("Entfernen", () => changeParts(side, index, 0)));
        parts.append(li);
    });
    if (block.parts.length) {
        preview.textContent = block.parts.map(id => {
            const part = find(id);
            return part ? part.text : "[Bestandteil nicht gefunden: " + id + "]";
        }).join("\n\n");
    }
}
function clean() {
    if (state.left.dirty || state.right.dirty) {
        message("Bitte erst beide bearbeiteten Blöcke speichern, bevor du die Beziehung oder Reihenfolge änderst.");
        return false;
    }
    return true;
}
async function run(operation, success) {
    try { message(""); await operation(); message(success); }
    catch (error) { message(error.message); }
}
async function save(side) {
    const current = state[side], block = find(current.id);
    const payload = {title:element(side,"title").value, text:element(side,"text").value};
    await run(async () => {
        const saved = block ? await request("save", {id:block.id, revision:current.revision, ...payload})
                            : await request("create", payload);
        current.id = saved.id; current.dirty = false;
        await refresh(); render(side);
        const other = side === "left" ? "right" : "left";
        if (!state[other].dirty) render(other);
    }, "Block gespeichert.");
}
async function changeParts(side, index, direction) {
    if (!clean()) return;
    const block = find(state[side].id), parts = [...block.parts];
    if (direction === 0) parts.splice(index, 1);
    else [parts[index], parts[index + direction]] = [parts[index + direction], parts[index]];
    await run(async () => {
        await request("parts", {id:block.id, revision:block.revision, parts});
        await refresh(); render("left"); render("right");
    }, "Reihenfolge gespeichert.");
}
async function removeRelation(side, index) {
    if (!clean()) return;
    const block = find(state[side].id);
    await run(async () => {
        await request("unrelate", {id:block.id, revision:block.revision, index});
        await refresh(); render("left"); render("right");
    }, "Beziehung entfernt.");
}
for (const side of ["left", "right"]) {
    for (const field of ["title", "text"]) element(side,field).addEventListener("input", () => state[side].dirty = true);
    element(side,"select").addEventListener("change", event => {
        openBlock(side, event.target.value);
    });
    element(side,"new").addEventListener("click", () => {
        if (state[side].dirty && !confirm("Ungespeicherte Änderungen verwerfen?")) return;
        state[side] = {id:"", revision:"", dirty:false}; render(side);
    });
    element(side,"save").addEventListener("click", () => save(side));
}
document.getElementById("block-search").addEventListener("input", renderBrowser);
async function relate(source, target) {
    await run(async () => {
    if (!clean()) throw new Error(status.textContent);
    const from = find(state[source].id), to = find(state[target].id);
    if (!from || !to) throw new Error("Bitte zuerst beide Blöcke speichern und auswählen.");
    await request("relate", {id:from.id, revision:from.revision, target:to.id, type:document.getElementById("type").value});
    await refresh(); render("left"); render("right");
    }, "Beziehung gespeichert.");
}
document.getElementById("relate").addEventListener("click", () => relate("left", "right"));
document.getElementById("relate-reverse").addEventListener("click", () => relate("right", "left"));
document.getElementById("part").addEventListener("click", () => run(async () => {
    if (!clean()) throw new Error(status.textContent);
    const left = find(state.left.id), right = find(state.right.id);
    if (!left || !right) throw new Error("Bitte zuerst beide Blöcke speichern und auswählen.");
    await request("parts", {id:left.id, revision:left.revision, parts:[...left.parts, right.id]});
    await refresh(); render("left"); render("right");
}, "Bestandteil hinzugefügt."));
window.addEventListener("beforeunload", event => {
    if (state.left.dirty || state.right.dirty) { event.preventDefault(); event.returnValue = ""; }
});
run(async () => { await refresh(); render("left"); render("right"); }, "");
