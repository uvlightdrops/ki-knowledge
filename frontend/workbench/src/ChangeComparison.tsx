import { useEffect, useRef } from "react";
import * as monaco from "monaco-editor/esm/vs/editor/editor.api";

type Props = { original: string; replacement: string };

export function ChangeComparison({ original, replacement }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const editor = useRef<monaco.editor.IStandaloneDiffEditor>();
  useEffect(() => {
    if (!container.current) return;
    const before = monaco.editor.createModel(original, "markdown");
    const after = monaco.editor.createModel(replacement, "markdown");
    const instance = monaco.editor.createDiffEditor(container.current, {
      readOnly: true, domReadOnly: true, originalEditable: false,
      automaticLayout: true, renderSideBySide: false, wordWrap: "on",
      minimap: { enabled: false }, scrollBeyondLastLine: false,
      accessibilitySupport: "on", theme: "vs-dark",
      originalAriaLabel: "Original der ausgewählten Passage",
      modifiedAriaLabel: "Vorgeschlagener Ersatz der Passage",
    });
    instance.setModel({ original: before, modified: after });
    editor.current = instance;
    return () => {
      instance.dispose(); before.dispose(); after.dispose(); editor.current = undefined;
    };
  }, []);
  useEffect(() => {
    const model = editor.current?.getModel();
    if (model?.original.getValue() !== original) model?.original.setValue(original);
    if (model?.modified.getValue() !== replacement) model?.modified.setValue(replacement);
  }, [original, replacement]);
  return <div ref={container} className="wb-diff" data-testid="proposal-diff" />;
}
