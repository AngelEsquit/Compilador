// Logica pura (sin React) de la vista de registros de activacion: convierte el `layout` que
// devuelve el bridge en filas ordenadas por offset, con el relleno de alineacion explicito.
import type { CompiscriptActivationRecord, CompiscriptClassLayout, CompiscriptLayout, CompiscriptSlot } from "./types";

export type FrameRowKind = "control" | "param" | "local" | "temp" | "padding" | "global" | "header" | "field";

export type FrameEntry = {
  name: string;
  type?: string;
};

export type FrameRow = {
  kind: FrameRowKind;
  offset: number;
  size: number;
  /** Casi siempre una; varias cuando bloques hermanos reutilizan el mismo espacio del frame. */
  entries: FrameEntry[];
  shared: boolean;
};

const WORD = 8;

function slotRow(kind: FrameRowKind, slot: CompiscriptSlot): FrameRow {
  return { kind, offset: slot.offset, size: slot.size, entries: [{ name: slot.name, type: slot.type }], shared: false };
}

/**
 * Agrupa los slots que se solapan. Los bloques hermanos (el `then` y el `else` de un `if`, por
 * ejemplo) empiezan en el mismo offset: ocupan la misma zona del frame en momentos distintos.
 */
function mergeOverlapping(kind: FrameRowKind, slots: CompiscriptSlot[]): FrameRow[] {
  const sorted = [...slots].sort((a, b) => a.offset - b.offset || a.size - b.size);
  const rows: FrameRow[] = [];
  for (const slot of sorted) {
    const last = rows[rows.length - 1];
    if (last && slot.offset < last.offset + last.size) {
      last.entries.push({ name: slot.name, type: slot.type });
      last.size = Math.max(last.offset + last.size, slot.offset + slot.size) - last.offset;
      last.shared = true;
    } else {
      rows.push(slotRow(kind, slot));
    }
  }
  return rows;
}

/** Inserta filas de relleno donde la alineacion deja huecos, y hasta completar `total` bytes. */
function fillGaps(rows: FrameRow[], total: number): FrameRow[] {
  const sorted = [...rows].sort((a, b) => a.offset - b.offset);
  const result: FrameRow[] = [];
  let cursor = 0;
  for (const row of sorted) {
    if (row.offset > cursor) {
      result.push({ kind: "padding", offset: cursor, size: row.offset - cursor, entries: [{ name: "relleno" }], shared: false });
    }
    result.push(row);
    cursor = Math.max(cursor, row.offset + row.size);
  }
  if (cursor < total) {
    result.push({ kind: "padding", offset: cursor, size: total - cursor, entries: [{ name: "relleno" }], shared: false });
  }
  return result;
}

/** Filas del registro de activacion: control, parametros, locales, temporales y relleno. */
export function recordRows(record: CompiscriptActivationRecord): FrameRow[] {
  const rows: FrameRow[] = [];
  for (const field of record.control) {
    rows.push({ kind: "control", offset: field.offset, size: field.size, entries: [{ name: field.name }], shared: false });
  }
  for (const param of record.params) {
    rows.push(slotRow("param", param));
  }
  rows.push(...mergeOverlapping("local", record.locals));
  for (let index = 0; index < record.temps.count; index++) {
    rows.push({
      kind: "temp",
      offset: record.temps.offset + index * record.temps.size,
      size: record.temps.size,
      entries: [{ name: `t${index}` }],
      shared: false,
    });
  }
  return fillGaps(rows, record.frameSize);
}

/** Area estatica donde viven las variables globales. */
export function staticRows(dataArea: CompiscriptLayout["dataArea"]): FrameRow[] {
  return fillGaps(
    dataArea.symbols.map((slot) => slotRow("global", slot)),
    dataArea.size
  );
}

/** Instancia de una clase: cabecera con el puntero a la clase y despues los campos. */
export function objectRows(cls: CompiscriptClassLayout): FrameRow[] {
  const rows: FrameRow[] = [
    { kind: "header", offset: 0, size: WORD, entries: [{ name: "puntero a la clase" }], shared: false },
    ...cls.fields.map((field) => slotRow("field", field)),
  ];
  return fillGaps(rows, cls.size);
}

/** Un metodo es heredado cuando su etiqueta no empieza por el nombre de la propia clase. */
export function inheritedFrom(cls: CompiscriptClassLayout, label: string): string | null {
  const owner = label.split(".")[0];
  return owner !== cls.name ? owner : null;
}
