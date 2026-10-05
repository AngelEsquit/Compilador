// Rubrica: trycatch (errores de ejecucion)
// expect: division por cero
let cero: integer = 0;
try {
  print(7 % cero);
} catch (e) {
  print(e);
}
