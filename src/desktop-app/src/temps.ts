// Logica pura (sin React) de la vista de temporales: calcula, para cada funcion, los "valores"
// intermedios que se guardaron en temporales y cuantos nombres de temporal bastaron para ellos.
//
// Un valor es lo que producen una o varias definiciones de un temporal que alcanzan a un mismo
// uso. Con `a || b` (o un ternario) el temporal se define en dos ramas y se usa despues de
// juntarlas: son dos instrucciones pero un solo valor. Por eso no basta con mirar el codigo en
// orden lineal: se hace un analisis de definiciones alcanzables sobre el grafo de flujo.
import type { CompiscriptScope, CompiscriptTACInstruction } from "./types";

export type TempValue = {
  temp: string;
  /** Indices (dentro del arreglo de instrucciones) donde se define. Varios si hay ramas. */
  defs: number[];
  /** Indices donde se usa. Vacio si el valor se calcula y se descarta (p. ej. `hola();`). */
  uses: number[];
  /** Primer y ultimo indice en que el valor existe. */
  start: number;
  end: number;
};

export type TempAnalysis = {
  values: TempValue[];
  /** Nombres de temporal distintos, ordenados numericamente. */
  names: string[];
  /** Usos sin ninguna definicion que los alcance. Debe estar vacio en codigo bien formado. */
  orphanUses: Array<{ temp: string; index: number }>;
};

const TEMP_NAME = /^t\d+$/;

// Instrucciones cuyo `result` es un temporal recien calculado.
const DEFINING_OPS = new Set([
  "copy",
  "+",
  "-",
  "*",
  "/",
  "%",
  "<",
  "<=",
  ">",
  ">=",
  "==",
  "!=",
  "neg",
  "not",
  "array",
  "length",
  "index_load",
  "member_load",
  "new",
  "env_load",
  "call_result",
  "invoke",
]);

type Field = "arg1" | "arg2" | "result";

// Campos que una instruccion LEE como operando (los nombres de campo, clases y etiquetas no cuentan).
const BINARY_FIELDS: Field[] = ["arg1", "arg2"];
const USE_FIELDS: Record<string, Field[]> = {
  copy: ["arg1"],
  neg: ["arg1"],
  not: ["arg1"],
  length: ["arg1"],
  array: ["arg1"],
  index_load: ["arg1", "arg2"],
  index_store: ["arg1", "arg2", "result"],
  member_load: ["arg1"],
  member_store: ["arg2", "result"],
  env_store: ["arg1"],
  call_result: ["arg1"],
  invoke: ["arg1"],
  param: ["arg1"],
  return: ["arg1"],
  print: ["arg1"],
  if: ["arg1"],
  ifFalse: ["arg1"],
};
for (const op of ["+", "-", "*", "/", "%", "<", "<=", ">", ">=", "==", "!="]) {
  USE_FIELDS[op] = BINARY_FIELDS;
}

/** Nombres que el programa declara (variables, parametros, campos): un `t0` asi no es un temporal. */
export function collectUserNames(scope: CompiscriptScope | undefined, into: Set<string> = new Set()): Set<string> {
  if (!scope) {
    return into;
  }
  Object.keys(scope.symbols ?? {}).forEach((name) => into.add(name));
  (scope.children ?? []).forEach((child) => collectUserNames(child, into));
  return into;
}

function tempsIn(instruction: CompiscriptTACInstruction, field: Field, userNames: ReadonlySet<string>): string[] {
  const raw = instruction[field];
  if (!raw) {
    return [];
  }
  // `array t0, t1` lista varios operandos; `invoke t0.metodo` lleva el receptor antes del punto.
  const parts =
    instruction.op === "array" && field === "arg1"
      ? raw.split(", ")
      : instruction.op === "invoke" && field === "arg1"
        ? [raw.split(".")[0]]
        : [raw];
  return parts.filter((part) => TEMP_NAME.test(part) && !userNames.has(part));
}

function usesOf(instruction: CompiscriptTACInstruction, userNames: ReadonlySet<string>): string[] {
  const fields = USE_FIELDS[instruction.op] ?? [];
  return fields.flatMap((field) => tempsIn(instruction, field, userNames));
}

function defOf(instruction: CompiscriptTACInstruction, userNames: ReadonlySet<string>): string | null {
  if (!DEFINING_OPS.has(instruction.op)) {
    return null;
  }
  const temp = instruction.result;
  return TEMP_NAME.test(temp) && !userNames.has(temp) ? temp : null;
}

const NO_FALLTHROUGH = new Set(["goto", "return", "halt", "end_function"]);

/** Sucesores de cada instruccion dentro del rango [start, end) (el grafo de flujo de control). */
function successors(tac: CompiscriptTACInstruction[], start: number, end: number): number[][] {
  const labels = new Map<string, number>();
  for (let index = start; index < end; index++) {
    if (tac[index].op === "label") {
      labels.set(tac[index].result, index);
    }
  }
  const result: number[][] = [];
  for (let index = start; index < end; index++) {
    const { op, result: target } = tac[index];
    const next: number[] = [];
    if (op === "goto" || op === "if" || op === "ifFalse" || op === "try") {
      const destination = labels.get(target);
      if (destination !== undefined) {
        next.push(destination);
      }
    }
    if (!NO_FALLTHROUGH.has(op) && index + 1 < end) {
      next.push(index + 1);
    }
    result.push(next);
  }
  return result;
}

/** Analiza el rango [start, end) de instrucciones: una funcion, o el programa principal. */
export function analyzeTemps(
  tac: CompiscriptTACInstruction[],
  start: number,
  end: number,
  userNames: ReadonlySet<string> = new Set()
): TempAnalysis {
  const size = end - start;
  const edges = successors(tac, start, end);
  const defs = Array.from({ length: size }, (_, offset) => defOf(tac[start + offset], userNames));

  // Definiciones alcanzables: reaching[i] = temporal -> indices de las definiciones que llegan a i.
  const reaching: Array<Map<string, Set<number>>> = Array.from({ length: size }, () => new Map());
  const outOf = (offset: number): Map<string, Set<number>> => {
    const out = new Map<string, Set<number>>();
    reaching[offset].forEach((set, temp) => out.set(temp, new Set(set)));
    const defined = defs[offset];
    if (defined) {
      out.set(defined, new Set([start + offset])); // la nueva definicion mata a las anteriores
    }
    return out;
  };

  let changed = true;
  while (changed) {
    changed = false;
    for (let offset = 0; offset < size; offset++) {
      const out = outOf(offset);
      for (const successor of edges[offset]) {
        const target = reaching[successor - start];
        out.forEach((set, temp) => {
          const current = target.get(temp) ?? new Set<number>();
          const before = current.size;
          set.forEach((definition) => current.add(definition));
          if (current.size !== before || !target.has(temp)) {
            target.set(temp, current);
            changed = true;
          }
        });
      }
    }
  }

  // Union-find sobre las definiciones: las que alcanzan un mismo uso son un solo valor.
  const parent = new Map<number, number>();
  const find = (x: number): number => {
    let root = x;
    while (parent.get(root) !== root) {
      root = parent.get(root) as number;
    }
    parent.set(x, root);
    return root;
  };
  const union = (a: number, b: number) => parent.set(find(a), find(b));
  defs.forEach((temp, offset) => {
    if (temp) {
      parent.set(start + offset, start + offset);
    }
  });

  const orphanUses: TempAnalysis["orphanUses"] = [];
  const usesByDef = new Map<number, number[]>();
  for (let offset = 0; offset < size; offset++) {
    for (const temp of usesOf(tac[start + offset], userNames)) {
      const reachable = [...(reaching[offset].get(temp) ?? [])];
      if (reachable.length === 0) {
        orphanUses.push({ temp, index: start + offset });
        continue;
      }
      reachable.slice(1).forEach((definition) => union(reachable[0], definition));
      usesByDef.set(reachable[0], [...(usesByDef.get(reachable[0]) ?? []), start + offset]);
    }
  }

  const grouped = new Map<number, TempValue>();
  defs.forEach((temp, offset) => {
    if (!temp) {
      return;
    }
    const definition = start + offset;
    const root = find(definition);
    const value = grouped.get(root) ?? { temp, defs: [], uses: [], start: definition, end: definition };
    value.defs.push(definition);
    grouped.set(root, value);
  });
  usesByDef.forEach((uses, definition) => {
    const value = grouped.get(find(definition));
    if (value) {
      value.uses.push(...uses);
    }
  });
  const values = [...grouped.values()].map((value) => {
    const uses = [...new Set(value.uses)].sort((a, b) => a - b);
    const defsSorted = [...value.defs].sort((a, b) => a - b);
    return {
      ...value,
      defs: defsSorted,
      uses,
      start: defsSorted[0],
      end: Math.max(defsSorted[defsSorted.length - 1], uses[uses.length - 1] ?? -1),
    };
  });
  values.sort((a, b) => a.start - b.start);

  const names = [...new Set(values.map((value) => value.temp))].sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)));
  return { values, names, orphanUses };
}
