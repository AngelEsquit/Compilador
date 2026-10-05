// Rubrica: trycatch (errores de ejecucion)
// expect: division por cero
// expect: paso
// expect: 5
function nivel2(d: integer): integer {
  return 10 / d;
}
function nivel1(d: integer): integer {
  let r: integer = nivel2(d);
  print("paso");
  return r;
}
try {
  print(nivel1(0));
} catch (e) {
  print(e);
}
print(nivel1(2));
