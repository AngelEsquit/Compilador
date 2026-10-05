import { useMemo } from "react";
import { groupTac, type TacGroup } from "./tac";
import { analyzeTemps, collectUserNames, type TempAnalysis, type TempValue } from "./temps";
import type { CompiscriptScope, CompiscriptTACInstruction } from "./types";

type GroupAnalysis = { group: TacGroup; analysis: TempAnalysis };

function pluralize(count: number, singular: string, plural: string) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function describe(value: TempValue, number: number, lines: string[]): string {
  const at = (index: number) => `${index + 1}${lines[index] ? ` (${lines[index]})` : ""}`;
  const defined = value.defs.length > 1 ? `definido en las líneas ${value.defs.map((d) => d + 1).join(", ")}` : `definido en la línea ${at(value.defs[0])}`;
  const used = value.uses.length === 0 ? "no se usa: el resultado se descarta" : `usado en ${value.uses.length === 1 ? "la línea" : "las líneas"} ${value.uses.map((u) => u + 1).join(", ")}`;
  return `${value.temp}, valor ${number}: ${defined}; ${used}`;
}

function TempRow({
  name,
  values,
  group,
  lines,
}: {
  name: string;
  values: TempValue[];
  group: TacGroup;
  lines: string[];
}) {
  const size = group.end - group.start;
  const percent = (index: number) => `${((index - group.start) / size) * 100}%`;
  return (
    <div className="tm-row">
      <span className="tm-name">
        <strong>{name}</strong>
        {values.length > 1 && <span className="tm-badge">{values.length} valores</span>}
      </span>
      <div className="tm-track">
        {values.map((value, position) => (
          <div
            key={value.start}
            className={`tm-bar tm-c${position % 4} ${value.uses.length === 0 ? "tm-dead" : ""}`}
            style={{ left: percent(value.start), width: `max(6px, ${((value.end - value.start + 1) / size) * 100}%)` }}
            title={describe(value, position + 1, lines)}
          >
            {value.defs.map((definition) => (
              <span key={`d${definition}`} className="tm-def" style={{ left: `calc(${((definition - value.start) / (value.end - value.start + 1)) * 100}% )` }} />
            ))}
            {value.uses.map((use) => (
              <span key={`u${use}`} className="tm-use" style={{ left: `${((use - value.start) / (value.end - value.start + 1)) * 100}%` }} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Vista "Temporales": para cada funcion, una fila por temporal con una barra por cada valor que
 * guardo. Varias barras en la misma fila significan que el temporal se reciclo.
 */
export function TempsView({
  tac,
  text,
  symbols,
}: {
  tac: CompiscriptTACInstruction[];
  text: string;
  symbols: CompiscriptScope | undefined;
}) {
  const lines = useMemo(() => text.split("\n"), [text]);
  const groups = useMemo<GroupAnalysis[]>(() => {
    const userNames = collectUserNames(symbols);
    return groupTac(tac).map((group) => ({ group, analysis: analyzeTemps(tac, group.start, group.end, userNames) }));
  }, [tac, symbols]);

  const withTemps = groups.filter(({ analysis }) => analysis.values.length > 0);
  const values = withTemps.reduce((total, { analysis }) => total + analysis.values.length, 0);
  const used = withTemps.reduce((total, { analysis }) => total + analysis.names.length, 0);
  const saved = values - used;

  if (values === 0) {
    return (
      <div className="validation-panel">
        <div className="validation-item ok">
          <span className="validation-item-title">Este programa no necesita temporales.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="tm-view">
      <div className="tm-summary">
        <div className="tm-figures">
          <span>
            <strong>{values}</strong> resultados intermedios
          </span>
          <span>
            <strong>{used}</strong> temporales usados
          </span>
          <span className="tm-saved">
            <strong>{saved}</strong> reutilizaciones ({Math.round((saved / values) * 100)} %)
          </span>
        </div>
        <div className="tm-meter" title="Temporales usados frente a los que haría falta sin reciclar">
          <div className="tm-meter-fill" style={{ width: `${(used / values) * 100}%` }} />
        </div>
        <div className="tm-note">
          Cada barra es un valor intermedio, desde que se calcula hasta su último uso. Varias barras en una misma fila
          significan que el temporal se reutilizó. El punto marca la definición y la raya cada uso; un borde
          punteado indica un resultado que se descarta.
        </div>
      </div>

      {withTemps.map(({ group, analysis }) => {
        const byName = new Map<string, TempValue[]>();
        analysis.values.forEach((value) => byName.set(value.temp, [...(byName.get(value.temp) ?? []), value]));
        return (
          <details key={`${group.kind}-${group.name}-${group.start}`} className="tac-group" open>
            <summary className="tac-group-title">
              <strong>{group.kind === "main" ? "Programa principal" : group.name}</strong>
              <span className="fr-chip">
                {pluralize(analysis.values.length, "valor", "valores")} → {pluralize(analysis.names.length, "temporal", "temporales")}
              </span>
              {analysis.values.length > analysis.names.length && (
                <span className="tac-group-meta">
                  se reciclan {analysis.values.length - analysis.names.length}
                </span>
              )}
            </summary>
            <div className="tm-rows">
              <div className="tm-axis">
                <span />
                <span className="tm-axis-line">
                  <span>línea {group.start + 1}</span>
                  <span>línea {group.end}</span>
                </span>
              </div>
              {analysis.names.map((name) => (
                <TempRow key={name} name={name} values={byName.get(name) ?? []} group={group} lines={lines} />
              ))}
            </div>
          </details>
        );
      })}
    </div>
  );
}
