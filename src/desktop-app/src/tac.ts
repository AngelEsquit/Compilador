// Logica pura (sin React) de la vista del codigo intermedio: agrupar las instrucciones por
// funcion y partir cada linea en piezas con su clase de color y, si corresponde, su destino.
import type { CompiscriptTACInstruction } from "./types";

export type TacGroup = {
  name: string;
  kind: "main" | "function";
  /** Rango [start, end) de indices dentro del arreglo de instrucciones. */
  start: number;
  end: number;
};

export type TacTokenKind = "kw" | "temp" | "num" | "str" | "label" | "link" | "up" | "name" | "text";

export type TacToken = {
  text: string;
  kind: TacTokenKind;
  /** Solo en `link`: a donde lleva el clic. */
  target?: string;
  targetKind?: "label" | "function";
};

const JUMP_OPS = new Set(["goto", "if", "ifFalse", "try"]);

const KEYWORDS = new Set([
  "if",
  "ifFalse",
  "goto",
  "try",
  "endtry",
  "halt",
  "function",
  "end",
  "param_decl",
  "param",
  "link",
  "call",
  "invoke",
  "return",
  "print",
  "array",
  "length",
  "new",
]);

const LITERAL_WORDS = new Set(["true", "false", "null"]);

/**
 * Separa el programa principal (todo lo anterior a la primera `function`) y cada funcion o
 * metodo. El generador emite los cuerpos de funcion despues del `halt` del programa principal,
 * uno tras otro, asi que cada grupo es un rango contiguo.
 */
export function groupTac(tac: CompiscriptTACInstruction[]): TacGroup[] {
  if (tac.length === 0) {
    return [];
  }
  const starts: number[] = [];
  tac.forEach((instruction, index) => {
    if (instruction.op === "function") {
      starts.push(index);
    }
  });

  const groups: TacGroup[] = [];
  const firstFunction = starts.length > 0 ? starts[0] : tac.length;
  if (firstFunction > 0) {
    groups.push({ name: "main", kind: "main", start: 0, end: firstFunction });
  }
  starts.forEach((start, position) => {
    const end = position + 1 < starts.length ? starts[position + 1] : tac.length;
    groups.push({ name: tac[start].result, kind: "function", start, end });
  });
  return groups;
}

// Cadena | temporal | up(n) | numero | identificador (admite `outer.inner`, `o.f`, `f.h#2`) | espacio | otro
const TOKEN = /("(?:[^"\\]|\\.)*")|(\bt\d+\b)|(\bup\(\d+\))|(\d+(?:\.\d+)?)|([A-Za-z_][A-Za-z0-9_]*(?:[.#][A-Za-z0-9_]+)*)|(\s+)|(.)/g;

/**
 * Parte una linea de TAC en piezas. `instruction` es la cuadrupla de esa linea: se usa para saber
 * a que etiqueta salta un `goto`/`if`/`ifFalse`/`try`, y `functions` para enlazar un `call` con el
 * cuerpo de la funcion llamada.
 */
export function tokenizeLine(
  line: string,
  instruction: CompiscriptTACInstruction | undefined,
  functions: ReadonlySet<string>
): TacToken[] {
  const tokens: TacToken[] = [];
  let labelDefined = false;

  for (const match of line.matchAll(TOKEN)) {
    const [text, str, temp, up, num, word] = match;
    if (str !== undefined) {
      tokens.push({ text, kind: "str" });
    } else if (temp !== undefined) {
      tokens.push({ text, kind: "temp" });
    } else if (up !== undefined) {
      tokens.push({ text, kind: "up" });
    } else if (num !== undefined) {
      tokens.push({ text, kind: "num" });
    } else if (word !== undefined) {
      if (instruction?.op === "label" && !labelDefined) {
        labelDefined = true;
        tokens.push({ text, kind: "label" });
      } else if (instruction && JUMP_OPS.has(instruction.op) && text === instruction.result) {
        tokens.push({ text, kind: "link", target: text, targetKind: "label" });
      } else if (instruction?.op === "call_result" && text === instruction.arg1 && functions.has(text)) {
        tokens.push({ text, kind: "link", target: text, targetKind: "function" });
      } else if (KEYWORDS.has(text)) {
        tokens.push({ text, kind: "kw" });
      } else if (LITERAL_WORDS.has(text)) {
        tokens.push({ text, kind: "num" });
      } else {
        tokens.push({ text, kind: "name" });
      }
    } else {
      tokens.push({ text, kind: "text" });
    }
  }
  return tokens;
}
