import { useEffect, useRef } from "react";
import * as monaco from "monaco-editor/esm/vs/editor/editor.api";
import "monaco-editor/esm/vs/basic-languages/markdown/markdown.contribution";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import { selectionAnchor, utf16Range } from "./coordinates.mjs";
import type { Anchor, Annotation } from "./types";

self.MonacoEnvironment = { getWorker: () => new EditorWorker() };

type Props = {
  text: string;
  annotations: Annotation[];
  selected: Annotation | null;
  readOnly?: boolean;
  onChange?: (text: string) => void;
  onSelection: (anchor: Anchor | null) => void;
  onError: (message: string) => void;
};

export function SourceEditor({ text, annotations, selected, readOnly = true, onChange, onSelection, onError }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const editor = useRef<monaco.editor.IStandaloneCodeEditor>();
  const callbacks = useRef({ onSelection, onError, onChange });
  callbacks.current = { onSelection, onError, onChange };
  useEffect(() => {
    if (!container.current) return;
    const model = monaco.editor.createModel(text, "markdown");
    const instance = monaco.editor.create(container.current, {
      model,
      readOnly,
      domReadOnly: readOnly,
      automaticLayout: true,
      minimap: { enabled: false },
      wordWrap: "on",
      scrollBeyondLastLine: false,
      fontSize: 15,
      accessibilitySupport: "on",
      ariaLabel: readOnly
        ? "Markdown-Snapshot, schreibgeschützt. Text auswählen und anschließend Als Block markieren verwenden."
        : "Markdown-Arbeitskopie. Änderungen ausdrücklich speichern.",
      theme: "vs-dark",
    });
    editor.current = instance;
    const listener = instance.onDidChangeCursorSelection(event => {
      if (event.selection.isEmpty()) {
        callbacks.current.onSelection(null);
        return;
      }
      try {
        callbacks.current.onSelection(selectionAnchor(
          model.getValue(),
          model.getOffsetAt(event.selection.getStartPosition()),
          model.getOffsetAt(event.selection.getEndPosition()),
        ));
      } catch (error) {
        callbacks.current.onError(error instanceof Error ? error.message : String(error));
      }
    });
    const changeListener = model.onDidChangeContent(() => callbacks.current.onChange?.(model.getValue()));
    return () => { changeListener.dispose(); listener.dispose(); instance.dispose(); model.dispose(); editor.current = undefined; };
  }, []);
  useEffect(() => {
    const model = editor.current?.getModel();
    if (model && model.getValue() !== text) model.setValue(text);
  }, [text]);
  useEffect(() => {
    editor.current?.updateOptions({ readOnly, domReadOnly: readOnly });
  }, [readOnly]);
  useEffect(() => {
    const instance = editor.current;
    const model = instance?.getModel();
    if (!instance || !model) return;
    const decorations = instance.createDecorationsCollection(annotations.map(annotation => {
      const [start, end] = utf16Range(text, annotation.start, annotation.end);
      return {
        range: monaco.Range.fromPositions(model.getPositionAt(start), model.getPositionAt(end)),
        options: {
          inlineClassName: annotation.id === selected?.id ? "wb-mark wb-mark-selected" : "wb-mark",
          hoverMessage: { value: annotation.title || "Markierter Block", supportHtml: false },
        },
      };
    }));
    return () => decorations.clear();
  }, [text, annotations, selected]);
  useEffect(() => {
    const instance = editor.current;
    const model = instance?.getModel();
    if (!selected || !instance || !model) return;
    const [start, end] = utf16Range(text, selected.start, selected.end);
    instance.revealRangeInCenter(monaco.Range.fromPositions(model.getPositionAt(start), model.getPositionAt(end)));
  }, [text, selected]);
  return <div ref={container} className="wb-editor" data-testid="source-editor" />;
}
