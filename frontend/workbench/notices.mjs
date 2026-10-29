import { readFile, writeFile } from "node:fs/promises";

const notices = [];
for (const [name, files] of [
  ["react", ["LICENSE"]],
  ["react-dom", ["LICENSE"]],
  ["scheduler", ["LICENSE"]],
  ["monaco-editor", ["LICENSE", "ThirdPartyNotices.txt"]],
]) {
  for (const file of files) {
    notices.push(`${name} / ${file}\n\n${await readFile(new URL(`node_modules/${name}/${file}`, import.meta.url), "utf8")}`);
  }
}
await writeFile(
  new URL("../../ki_knowledge/django_site/static/django_site/workbench/THIRD-PARTY-NOTICES.txt", import.meta.url),
  notices.join("\n\n------------------------------------------------------------\n\n"),
);
