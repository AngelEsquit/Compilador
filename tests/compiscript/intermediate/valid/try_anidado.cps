// Rubrica: trycatch (errores de ejecucion)
// expect: interno
// expect: externo
let cero: integer = 0;
try {
  try {
    print(1 / cero);
  } catch (a) {
    print("interno");
    print(2 / cero);
  }
  print("no se imprime");
} catch (b) {
  print("externo");
}
