import { useMemo, useState } from "react";
import type { CompiscriptASMResult, CompiscriptActivation } from "./types";

// ---------------------------------------------------------------------------------------------
// Vista "Ensamblador": el MIPS generado. Cada instruccion del TAC aparece como comentario
// antes de las instrucciones MIPS que la traducen.
// ---------------------------------------------------------------------------------------------
type AsmLine =
  | { kind: "blank" }
  | { kind: "source" | "label" | "directive"; text: string }
  | { kind: "instr"; mnemonic: string; operands: string; comment: string; number: number };

function parseAsm(asm: string): AsmLine[] {
  let number = 0;
  return asm.split("\n").map((raw): AsmLine => {
    const text = raw.trim();
    if (!text) {
      return { kind: "blank" };
    }
    if (text.startsWith("#")) {
      return { kind: "source", text: text.slice(1).trim() };
    }
    if (text.startsWith(".")) {
      return { kind: "directive", text };
    }
    if (!raw.startsWith(" ") && text.endsWith(":")) {
      return { kind: "label", text };
    }
    const hash = text.indexOf("#");
    const code = hash >= 0 ? text.slice(0, hash).trim() : text;
    const space = code.indexOf(" ");
    number += 1;
    return {
      kind: "instr",
      mnemonic: space >= 0 ? code.slice(0, space) : code,
      operands: space >= 0 ? code.slice(space + 1) : "",
      comment: hash >= 0 ? text.slice(hash + 1).trim() : "",
      number,
    };
  });
}

// Registro | numero | resto
const OPERAND = /(\$[a-z0-9]+)|(-?\b\d+\b)|([^$\d-]+|.)/g;

function Operands({ text }: { text: string }) {
  return (
    <>
      {[...text.matchAll(OPERAND)].map(([piece, register, num], index) => (
        <span key={index} className={register ? "tac-tok-temp" : num ? "tac-tok-num" : "tac-tok-name"}>
          {piece}
        </span>
      ))}
    </>
  );
}

function AsmCodeView({ result }: { result: CompiscriptASMResult }) {
  const lines = useMemo(() => parseAsm(result.asm), [result.asm]);
  const [copied, setCopied] = useState(false);
  const [showSource, setShowSource] = useState(true);
  const applied = Object.entries(result.peephole ?? {}).filter(([, count]) => count > 0);

  async function copy() {
    try {
      await navigator.clipboard.writeText(result.asm);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="tac-view">
      <div className="tac-toolbar">
        <span className="tac-stats">
          {result.instructionCount ?? 0} instrucciones, {result.registers?.length ?? 0} registros asignables
          {applied.length > 0 && `, mirilla: ${applied.map(([name, count]) => `${name} x${count}`).join(", ")}`}
        </span>
        <span className="asm-actions">
          <button
            type="button"
            className={`result-view-btn ${showSource ? "active" : ""}`}
            onClick={() => setShowSource((value) => !value)}
            title="Muestra la instrucción del código intermedio que origina cada grupo"
          >
            Código intermedio
          </button>
          <button type="button" className="result-view-btn" onClick={() => void copy()}>
            {copied ? "Copiado" : "Copiar"}
          </button>
        </span>
      </div>
      <div className="tac-group">
        <div className="tac-lines">
          {lines.map((line, index) => {
            if (line.kind === "blank") {
              return <div key={index} className="tac-line asm-blank" />;
            }
            if (line.kind === "source") {
              return showSource ? (
                <div key={index} className="tac-line asm-source">
                  <span className="tac-num" />
                  <code className="tac-code">{line.text}</code>
                </div>
              ) : null;
            }
            if (line.kind !== "instr") {
              return (
                <div key={index} className={`tac-line ${line.kind === "label" ? "tac-line-label" : ""}`}>
                  <span className="tac-num" />
                  <code className={`tac-code ${line.kind === "label" ? "tac-tok-label" : "tac-tok-text"}`}>
                    {line.text}
                  </code>
                </div>
              );
            }
            return (
              <div key={index} className="tac-line">
                <span className="tac-num">{line.number}</span>
                <code className="tac-code">
                  <span className="tac-tok-kw asm-mnemonic">{line.mnemonic}</span>
                  <Operands text={line.operands} />
                  {line.comment && <span className="asm-comment">{line.comment}</span>}
                </code>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Vista "Ejecucion": lo que imprime el programa en el simulador.
// ---------------------------------------------------------------------------------------------
function ExecutionView({ result }: { result: CompiscriptASMResult }) {
  if (result.runError) {
    return (
      <div className="validation-panel">
        <div className="validation-item fail">
          <span className="validation-item-title">El simulador se detuvo</span>
          <span className="validation-item-detail">{result.runError}</span>
        </div>
      </div>
    );
  }
  const failed = (result.exitCode ?? 0) !== 0;
  return (
    <div className="tac-view">
      <div className="tac-toolbar">
        <span className="tac-stats">
          {result.steps ?? 0} instrucciones ejecutadas, código de salida {result.exitCode ?? 0}
        </span>
      </div>
      <pre className={`asm-output ${failed ? "asm-output-error" : ""}`}>{result.output || "(sin salida)"}</pre>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Vista "Arbol de activacion": una entrada por cada llamada que ocurrio durante la ejecucion.
// ---------------------------------------------------------------------------------------------
function measure(node: CompiscriptActivation): { count: number; depth: number } {
  let count = 1;
  let depth = 1;
  for (const child of node.children) {
    const inner = measure(child);
    count += inner.count;
    depth = Math.max(depth, inner.depth + 1);
  }
  return { count, depth };
}

function ActivationNode({ node }: { node: CompiscriptActivation }) {
  const title = (
    <>
      <strong>{node.name}</strong>
      <span className="tac-tok-name">({node.arguments.join(", ")})</span>
      {node.result !== null && <span className="act-result">= {node.result}</span>}
      <span className="tac-group-meta">registro de {node.frameSize} bytes</span>
    </>
  );
  if (node.children.length === 0) {
    return <div className="act-node act-leaf">{title}</div>;
  }
  return (
    <details className="act-node" open>
      <summary>{title}</summary>
      <div className="act-children">
        {node.children.map((child, index) => (
          <ActivationNode key={index} node={child} />
        ))}
      </div>
    </details>
  );
}

function ActivationTreeView({ tree }: { tree: CompiscriptActivation }) {
  const { count, depth } = useMemo(() => measure(tree), [tree]);
  return (
    <div className="tac-view">
      <div className="tac-toolbar">
        <span className="tac-stats">
          {count} activaciones, profundidad máxima {depth}
        </span>
      </div>
      <div className="tac-group act-tree">
        <ActivationNode node={tree} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Vista "Registros": decisiones del asignador (cargas, asignaciones, derrames y guardados).
// ---------------------------------------------------------------------------------------------
const EVENT_LABEL: Record<string, string> = {
  carga: "Carga desde memoria",
  asigna: "Asigna registro",
  derrame: "Derrame a memoria",
  guarda: "Guarda al cerrar bloque o llamar",
};

function RegistersView({ result }: { result: CompiscriptASMResult }) {
  const summary = result.allocationSummary ?? [];
  const [selected, setSelected] = useState<string>(summary[0]?.function ?? "");
  const events = useMemo(
    () => (result.allocation ?? []).filter((event) => event.function === selected),
    [result.allocation, selected]
  );

  return (
    <div className="tac-view">
      <div className="tac-toolbar">
        <span className="tac-stats">Registros asignables: {(result.registers ?? []).join(" ")}</span>
      </div>
      <table className="reg-table">
        <thead>
          <tr>
            <th>Función</th>
            <th>Cargas</th>
            <th>Asignaciones</th>
            <th>Derrames</th>
            <th>Guardados</th>
          </tr>
        </thead>
        <tbody>
          {summary.map((row) => (
            <tr
              key={row.function}
              className={row.function === selected ? "reg-selected" : ""}
              onClick={() => setSelected(row.function)}
            >
              <td>{row.function}</td>
              <td>{row.carga}</td>
              <td>{row.asigna}</td>
              <td className={row.derrame > 0 ? "reg-spill" : ""}>{row.derrame}</td>
              <td>{row.guarda}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {selected && (
        <div className="tac-group">
          <div className="tac-group-title">
            <strong>{selected}</strong>
            <span className="tac-group-meta">{events.length} decisiones, en orden de emisión</span>
          </div>
          <div className="tac-lines">
            {events.map((event, index) => (
              <div key={index} className={`tac-line ${event.event === "derrame" ? "reg-spill-line" : ""}`}>
                <span className="tac-num">{index + 1}</span>
                <code className="tac-code">
                  <span className="tac-tok-temp asm-mnemonic">{event.register}</span>
                  <span className="tac-tok-name asm-mnemonic">{event.variable}</span>
                  <span className="asm-comment">{EVENT_LABEL[event.event] ?? event.event}</span>
                </code>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Contenedor con pestanas del resultado de "Ensamblador".
// ---------------------------------------------------------------------------------------------
export function AsmResultView({ result }: { result: CompiscriptASMResult }) {
  const tabs: Array<{ id: string; label: string; render: () => JSX.Element }> = [
    { id: "asm", label: "Ensamblador", render: () => <AsmCodeView result={result} /> },
    { id: "run", label: "Ejecución", render: () => <ExecutionView result={result} /> },
  ];
  if (result.tree) {
    const tree = result.tree;
    tabs.push({ id: "tree", label: "Árbol de activación", render: () => <ActivationTreeView tree={tree} /> });
  }
  tabs.push({ id: "registers", label: "Registros", render: () => <RegistersView result={result} /> });
  const [active, setActive] = useState(tabs[0].id);
  const current = tabs.find((tab) => tab.id === active) ?? tabs[0];

  return (
    <div className="tac-result">
      <div className="tac-tabs" role="tablist" aria-label="Vistas del ensamblador">
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
      {current.render()}
    </div>
  );
}
