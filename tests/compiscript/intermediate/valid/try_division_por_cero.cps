// Rubrica: trycatch (errores de ejecucion)
// expect: antes
// expect: division por cero
// expect: fin
let cero: integer = 0;
try {
  print("antes");
  let x: integer = 10 / cero;
  print("no se imprime");
} catch (e) {
  print(e);
}
print("fin");
