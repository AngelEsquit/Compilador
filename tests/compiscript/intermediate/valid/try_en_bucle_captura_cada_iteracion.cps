// Rubrica: trycatch (errores de ejecucion)
// expect: 10
// expect: error
// expect: 5
// expect: error
// expect: fin
let ds: integer[] = [1, 0, 2, 0];
foreach (d in ds) {
  try {
    print(10 / d);
  } catch (e) {
    print("error");
  }
}
print("fin");
