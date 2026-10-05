// Rubrica: arreglos
// expect: 6
// expect: 3
function suma(v: integer[]): integer {
  let s: integer = 0;
  foreach (e in v) {
    s = s + e;
  }
  return s;
}
let a: integer[] = [1, 2, 3];
print(suma(a));
print(a[1 + 1]);
