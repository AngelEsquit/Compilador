// Rubrica: trycatch (errores de ejecucion)
// expect: 5
// expect: division por cero
// expect: siguiente
function dividir(a: integer, b: integer): integer {
  return a / b;
}
try {
  print(dividir(10, 2));
  print(dividir(10, 0));
  print("no se imprime");
} catch (e) {
  print(e);
}
print("siguiente");
