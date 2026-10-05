import { inheritedFrom, objectRows, recordRows, staticRows, type FrameRow, type FrameRowKind } from "./frames";
import type { CompiscriptActivationRecord, CompiscriptLayout } from "./types";

const KIND_LABEL: Record<FrameRowKind, string> = {
  control: "Control",
  param: "Parámetro",
  local: "Local",
  temp: "Temporal",
  padding: "Relleno",
  global: "Global",
  header: "Cabecera",
  field: "Campo",
};

const RECORD_KIND_LABEL: Record<string, string> = {
  main: "principal",
  function: "función",
  method: "método",
  constructor: "constructor",
};

function Rows({ rows, prefix }: { rows: FrameRow[]; prefix: string }) {
  return (
    <div className="fr-rows">
      {rows.map((row, index) => (
        <div key={`${row.kind}-${row.offset}-${index}`} className={`fr-row fr-${row.kind}`} title={KIND_LABEL[row.kind]}>
          <span className="fr-off">
            {prefix}+{row.offset}
          </span>
          <span className="fr-body">
            {row.entries.map((entry, position) => (
              <span key={position} className="fr-entry">
                <strong>{entry.name}</strong>
                {entry.type && <span className="fr-type">: {entry.type}</span>}
              </span>
            ))}
            {row.shared && (
              <span className="fr-badge" title="Bloques hermanos: usan la misma zona del frame, no a la vez">
                compartido
              </span>
            )}
          </span>
          <span className="fr-size">{row.size} B</span>
        </div>
      ))}
    </div>
  );
}

function RecordCard({ record }: { record: CompiscriptActivationRecord }) {
  return (
    <details className="tac-group" open>
      <summary className="tac-group-title">
        <strong>{record.kind === "main" ? "Programa principal" : record.name}</strong>
        <span className="fr-chip">{RECORD_KIND_LABEL[record.kind] ?? record.kind}</span>
        <span className="fr-chip">nivel {record.level}</span>
        {record.parent && <span className="fr-chip">dentro de {record.parent}</span>}
        <span className="tac-group-meta">{record.frameSize} bytes</span>
      </summary>
      <Rows rows={recordRows(record)} prefix="fp" />
    </details>
  );
}

/**
 * Vista "Registros de activacion": un diagrama por funcion con las zonas del frame (control,
 * parametros, locales, temporales y relleno de alineacion), el area estatica de las globales y la
 * distribucion de las clases con su tabla de metodos.
 */
export function FramesView({ layout }: { layout: CompiscriptLayout }) {
  const legend: FrameRowKind[] = ["control", "param", "local", "temp", "padding"];
  return (
    <div className="fr-view">
      <div className="fr-legend" aria-label="Leyenda">
        {legend.map((kind) => (
          <span key={kind} className={`fr-legend-item fr-${kind}`}>
            {KIND_LABEL[kind]}
          </span>
        ))}
        <span className="fr-legend-note">offsets en bytes desde fp</span>
      </div>

      {layout.dataArea.symbols.length > 0 && (
        <details className="tac-group" open>
          <summary className="tac-group-title">
            <strong>Área estática</strong>
            <span className="fr-chip">variables globales</span>
            <span className="tac-group-meta">{layout.dataArea.size} bytes</span>
          </summary>
          <Rows rows={staticRows(layout.dataArea)} prefix="global" />
        </details>
      )}

      {layout.records.map((record) => (
        <RecordCard key={record.name} record={record} />
      ))}

      {layout.classes.map((cls) => (
        <details key={cls.name} className="tac-group" open>
          <summary className="tac-group-title">
            <strong>clase {cls.name}</strong>
            {cls.superclass && <span className="fr-chip">hereda de {cls.superclass}</span>}
            <span className="tac-group-meta">{cls.size} bytes por instancia</span>
          </summary>
          <Rows rows={objectRows(cls)} prefix="obj" />
          {cls.methods.length > 0 && (
            <div className="fr-methods">
              <div className="fr-methods-title">Tabla de métodos</div>
              {cls.methods.map((method) => {
                const owner = inheritedFrom(cls, method.label);
                return (
                  <div key={method.slot} className="fr-method">
                    <span className="fr-off">[{method.slot}]</span>
                    <span className="fr-body">
                      <strong>{method.name}</strong>
                      <span className="fr-type"> → {method.label}</span>
                      {owner && <span className="fr-badge">heredado de {owner}</span>}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </details>
      ))}
    </div>
  );
}
