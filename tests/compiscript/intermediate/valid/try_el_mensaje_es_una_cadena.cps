// Rubrica: trycatch (errores de ejecucion)
// expect: fallo: division por cero
let cero: integer = 0;
try {
  print(1 % cero);
} catch (e) {
  print("fallo: " + e);
}
