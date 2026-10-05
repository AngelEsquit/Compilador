// Rubrica: trycatch (errores de ejecucion)
// expect: acceso a null
// expect: acceso a null
// expect: acceso a null
class A {
  let x: integer = 1;
  function f(): integer {
    return 1;
  }
}
let a: A = null;
try {
  print(a.x);
} catch (e) {
  print(e);
}
try {
  a.x = 5;
} catch (e) {
  print(e);
}
try {
  print(a.f());
} catch (e) {
  print(e);
}
