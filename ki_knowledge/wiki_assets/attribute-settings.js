"use strict";

const DEFAULT_HIDDEN_ATTRIBUTES = ["art", "project", "agent_project"];

function flattenAttributes(value, prefix = "", result = {}) {
    for (const [key, item] of Object.entries(value || {})) {
        const name = prefix ? prefix + "." + key : key;
        if (item && typeof item === "object" && !Array.isArray(item)) {
            if (Object.keys(item).length) flattenAttributes(item, name, result);
            else result[name] = "{}";
        } else {
            result[name] = item === null ? "null" : typeof item === "object" ? JSON.stringify(item) : String(item);
        }
    }
    return result;
}
function attributeShortName(name) { return name.split(".").pop(); }
function attributeSettingsKey(domainName) {
    return "wissenswiki.attributes.v1." + (domainName ? "domain." + domainName : "wiki");
}
// Liefert die ausgeblendeten Kurznamen; ohne gespeicherte Auswahl gelten die Standardwerte.
function loadHiddenAttributes(domainName) {
    const stored = JSON.parse(localStorage.getItem(attributeSettingsKey(domainName)) || "null");
    if (stored === null) return new Set(DEFAULT_HIDDEN_ATTRIBUTES);
    if (!stored || !Array.isArray(stored.hidden) || !stored.hidden.every(item => typeof item === "string")) {
        throw new Error("Ungültiges Format der Attributeinstellungen");
    }
    return new Set(stored.hidden);
}
function saveHiddenAttributes(domainName, hidden) {
    localStorage.setItem(attributeSettingsKey(domainName), JSON.stringify({hidden: [...hidden].sort()}));
}
