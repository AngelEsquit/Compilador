// Programa con varios errores semanticos independientes y de categorias
// distintas, usado para verificar que el analizador no se detiene en el
// primer error: debe seguir procesando y reportar todos los que encuentre
// en una misma ejecucion (Instrucciones.md, punto 12).

let x: integer = "no es un entero";

print(y);

class A {
  let z: integer;
  function constructor() {
    this.z = 1;
  }
}

let a: A = new A();
print(a.inexistente);

function f(a: integer): integer {
  return a;
}

f(1, 2, 3);

if (5) {
  print(1);
}
