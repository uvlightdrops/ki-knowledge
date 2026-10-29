export function selectionAnchor(text, startUtf16, endUtf16) {
  if (!Number.isInteger(startUtf16) || !Number.isInteger(endUtf16) ||
      startUtf16 < 0 || endUtf16 > text.length || startUtf16 >= endUtf16) {
    throw new Error("Bitte eine nicht leere Textstelle auswählen.");
  }
  for (const offset of [startUtf16, endUtf16]) {
    const previous = text.charCodeAt(offset - 1);
    const current = text.charCodeAt(offset);
    if (previous >= 0xd800 && previous <= 0xdbff && current >= 0xdc00 && current <= 0xdfff) {
      throw new Error("Die Auswahl teilt ein Unicode-Zeichen. Bitte erneut auswählen.");
    }
  }
  const points = Array.from(text);
  const start = Array.from(text.slice(0, startUtf16)).length;
  const end = Array.from(text.slice(0, endUtf16)).length;
  return {
    representation: "markdown-source-v1",
    offset_unit: "unicode-codepoint",
    start,
    end,
    exact: points.slice(start, end).join(""),
    prefix: points.slice(Math.max(0, start - 32), start).join(""),
    suffix: points.slice(end, end + 32).join(""),
  };
}

export function utf16Range(text, start, end) {
  const points = Array.from(text);
  return [
    points.slice(0, start).join("").length,
    points.slice(0, end).join("").length,
  ];
}
