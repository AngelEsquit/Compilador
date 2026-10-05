// Rubrica: trycatch (errores de ejecucion)
// expect: indice fuera de rango
// expect: 1
// expect: 2
let xs: integer[] = [1, 2];
try {
  xs[2] = 9;
} catch (e) {
  print(e);
}
print(xs[0]);
print(xs[1]);
