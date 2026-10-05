// Rubrica: trycatch (errores de ejecucion)
// expect: interno
// expect: despues
// expect: fin
let cero: integer = 0;
try {
  try {
    print(1 / cero);
  } catch (a) {
    print("interno");
  }
  print("despues");
} catch (b) {
  print("externo");
}
print("fin");
