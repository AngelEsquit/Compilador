// Rubrica: trycatch (errores de ejecucion)
// expect: division por cero
// expect: 50
class Calc {
  function dividir(a: integer, b: integer): integer {
    return a / b;
  }
}
let c: Calc = new Calc();
try {
  print(c.dividir(1, 0));
} catch (e) {
  print(e);
}
print(c.dividir(100, 2));
