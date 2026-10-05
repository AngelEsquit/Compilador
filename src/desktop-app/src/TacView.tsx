import { useEffect, useMemo, useRef, useState } from "react";
import { FramesView } from "./FramesView";
import { groupTac, tokenizeLine, type TacToken } from "./tac";
import { TempsView } from "./TempsView";
import type { CompiscriptTACInstruction, CompiscriptTACResult } from "./types";

// ---------------------------------------------------------------------------------------------
// Vista "Codigo": el TAC numerado y coloreado, agrupado por funcion, con los saltos y las
// llamadas como enlaces.
// ---------------------------------------------------------------------------------------------
function TacCodeView({ tac, text }: { tac: CompiscriptTACInstruction[]; text: string }) {
  const lines = useMemo(() => text.split("\n"), [text]);
  const groups = useMemo(() => groupTac(tac), [tac]);
  const functions = useMemo(
    () => new Set(groups.filter((group) => group.kind === "function").map((group) => group.name)),
    [groups]
  );
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [flash, setFlash] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // El resaltado de destino dura un instante.
  useEffect(() => {
    if (!flash) {
      return;
    }
    const timer = window.setTimeout(() => setFlash(null), 1400);
    return () => window.clearTimeout(timer);
  }, [flash]);

  function setOpen(name: string, open: boolean) {
    setCollapsed((previous) => {
      if (previous.has(name) === !open) {
        return previous;
      }
      const next = new Set(previous);
      if (open) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }

  function follow(token: TacToken) {
    if (!token.target) {
      return;
    }
    const anchor = token.targetKind === "function" ? `fn:${token.target}` : `label:${token.target}`;
    if (token.targetKind === "function") {
      setOpen(token.target, true); // el cuerpo puede estar plegado
    }
    setFlash(anchor);
    // Se espera al render para que un grupo recien abierto ya tenga su altura.
    window.requestAnimationFrame(() => {
      rootRef.current
        ?.querySelector(`[data-anchor="${CSS.escape(anchor)}"]`)
        ?.scrollIntoView({ block: "center", behavior: "smooth" });
    });
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  const functionCount = groups.filter((group) => group.kind === "function").length;

  return (
    <div className="tac-view" ref={rootRef}>
      <div className="tac-toolbar">
        <span className="tac-stats">
          {tac.length} instrucciones · {functionCount} {functionCount === 1 ? "función" : "funciones"}
        </span>
        <button type="button" className="result-view-btn" onClick={() => void copy()}>
          {copied ? "Copiado" : "Copiar"}
        </button>
      </div>

      {groups.map((group) => {
        const anchor = `fn:${group.name}`;
        return (
          <details
            key={`${group.kind}-${group.name}-${group.start}`}
            className="tac-group"
            open={!collapsed.has(group.name)}
            onToggle={(event) => setOpen(group.name, event.currentTarget.open)}
          >
            <summary
              className={`tac-group-title ${flash === anchor ? "tac-flash" : ""}`}
              data-anchor={anchor}
            >
              <strong>{group.kind === "main" ? "Programa principal" : group.name}</strong>
              <span className="tac-group-meta">{group.end - group.start} instrucciones</span>
            </summary>
            <div className="tac-lines">
              {tac.slice(group.start, group.end).map((instruction, offset) => {
                const index = group.start + offset;
                const isLabel = instruction.op === "label";
                const labelAnchor = isLabel ? `label:${instruction.result}` : undefined;
                return (
                  <div
                    key={index}
                    className={`tac-line ${isLabel ? "tac-line-label" : ""} ${
                      labelAnchor && flash === labelAnchor ? "tac-flash" : ""
                    }`}
                    data-anchor={labelAnchor}
                  >
                    <span className="tac-num">{index + 1}</span>
                    <code className="tac-code">
                      {tokenizeLine(lines[index] ?? "", instruction, functions).map((token, position) =>
                        token.kind === "link" ? (
                          <button
                            key={position}
                            type="button"
                            className="tac-link"
                            title={
                              token.targetKind === "function"
                                ? `Ir a la función ${token.target}`
                                : `Ir a la etiqueta ${token.target}`
                            }
                            onClick={() => follow(token)}
                          >
                            {token.text}
                          </button>
                        ) : (
                          <span key={position} className={`tac-tok tac-tok-${token.kind}`}>
                            {token.text}
                          </span>
                        )
                      )}
                    </code>
                  </div>
                );
              })}
            </div>
          </details>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Contenedor con pestanas. Cada vista del resultado de "Codigo Intermedio" es una entrada de
// `tabs`; la barra solo aparece cuando hay mas de una.
// ---------------------------------------------------------------------------------------------
export function TacResultView({ result }: { result: CompiscriptTACResult }) {
  const tabs: Array<{ id: string; label: string; render: () => JSX.Element }> = [
    { id: "code", label: "Código", render: () => <TacCodeView tac={result.tac} text={result.text} /> },
  ];
  if (result.layout) {
    const layout = result.layout;
    tabs.push({ id: "frames", label: "Registros de activación", render: () => <FramesView layout={layout} /> });
  }
  tabs.push({
    id: "temps",
    label: "Temporales",
    render: () => <TempsView tac={result.tac} text={result.text} symbols={result.symbols} />,
  });
  const [active, setActive] = useState(tabs[0].id);
  const current = tabs.find((tab) => tab.id === active) ?? tabs[0];

  return (
    <div className="tac-result">
      {tabs.length > 1 && (
        <div className="tac-tabs" role="tablist" aria-label="Vistas del código intermedio">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={tab.id === current.id}
              className={`result-tab-btn ${tab.id === current.id ? "active" : ""}`}
              onClick={() => setActive(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}
      {current.render()}
    </div>
  );
}
