// Rubrica: trycatch (errores de ejecucion)
// expect: 5
// expect: -1
function seguro(d: integer): integer {
  try {
    return 10 / d;
  } catch (e) {
    return -1;
  }
}
print(seguro(2));
print(seguro(0));
