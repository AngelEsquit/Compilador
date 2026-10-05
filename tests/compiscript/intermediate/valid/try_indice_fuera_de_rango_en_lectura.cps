// Rubrica: trycatch (errores de ejecucion)
// expect: indice fuera de rango
// expect: indice fuera de rango
// expect: 1
// expect: ok
let xs: integer[] = [1, 2, 3];
try {
  print(xs[5]);
} catch (e) {
  print(e);
}
try {
  print(xs[0 - 1]);
} catch (e) {
  print(e);
}
try {
  print(xs[2] - 2);
} catch (e) {
  print("no");
}
print("ok");
