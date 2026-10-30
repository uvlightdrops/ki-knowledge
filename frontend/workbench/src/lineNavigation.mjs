export function lineNavigation(text) {
  const count = text.split(/\r\n|\r|\n/).length;
  const targetStep = Math.max(1, Math.ceil(count / 20));
  const magnitude = 10 ** Math.floor(Math.log10(targetStep));
  const step = [1, 2, 5, 10].map(value => value * magnitude).find(value => value >= targetStep);
  const lines = [1];
  for (let line = step; line < count; line += step) {
    if (line > 1) lines.push(line);
  }
  if (count > 1) lines.push(count);
  return lines;
}
