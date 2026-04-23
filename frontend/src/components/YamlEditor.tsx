import { useMemo } from "react";
import CodeMirror, { EditorView } from "@uiw/react-codemirror";
import { yaml } from "@codemirror/lang-yaml";
import { oneDark } from "@codemirror/theme-one-dark";

type Props = {
  value: string;
  onChange: (value: string) => void;
  minHeight?: string;
  readOnly?: boolean;
  placeholder?: string;
};

/**
 * Thin wrapper around CodeMirror 6 configured for YAML editing. Matches
 * the slate palette used by the rest of the app (via the one-dark theme
 * plus a few style overrides) and exposes a plain
 * ``value`` / ``onChange`` surface so it drops in where a ``<textarea>``
 * used to live.
 *
 * Heights default to fill-parent — the caller controls layout via
 * wrapping CSS.
 */
export function YamlEditor({
  value,
  onChange,
  minHeight = "24rem",
  readOnly = false,
  placeholder,
}: Props) {
  const extensions = useMemo(
    () => [
      yaml(),
      EditorView.lineWrapping,
      EditorView.theme({
        "&": {
          fontSize: "12px",
          backgroundColor: "rgb(2 6 23)", // slate-950
        },
        ".cm-content": {
          fontFamily:
            "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace",
        },
        ".cm-gutters": {
          backgroundColor: "rgb(15 23 42)", // slate-900
          borderRight: "1px solid rgb(30 41 59)", // slate-800
        },
        "&.cm-focused": {
          outline: "none",
        },
      }),
    ],
    [],
  );

  return (
    <div
      className="overflow-hidden rounded-md border border-slate-700 focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500"
      style={{ minHeight }}
    >
      <CodeMirror
        value={value}
        onChange={onChange}
        extensions={extensions}
        theme={oneDark}
        readOnly={readOnly}
        placeholder={placeholder}
        basicSetup={{
          lineNumbers: true,
          foldGutter: true,
          highlightActiveLine: true,
          bracketMatching: true,
          tabSize: 2,
        }}
        style={{ minHeight }}
      />
    </div>
  );
}
