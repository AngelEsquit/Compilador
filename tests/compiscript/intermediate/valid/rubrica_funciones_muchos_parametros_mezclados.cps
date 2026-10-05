// Rubrica: funciones
// expect: ok
function f(a: integer, b: float, c: string, d: boolean): string {
  return c;
}
print(f(1, 2.5, "ok", true));
