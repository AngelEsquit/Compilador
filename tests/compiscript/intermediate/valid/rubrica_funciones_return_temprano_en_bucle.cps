// Rubrica: funciones
// expect: 2
// expect: -1
function buscar(xs: integer[], v: integer): integer {
  let i: integer = 0;
  foreach (e in xs) {
    if (e == v) {
      return i;
    }
    i = i + 1;
  }
  return -1;
}
print(buscar([5, 6, 7], 7));
print(buscar([1], 9));
