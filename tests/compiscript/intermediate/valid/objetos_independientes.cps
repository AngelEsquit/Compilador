// expect: 12
class Caja {
  let dato: integer = 0;
  function guardar(d: integer): integer {
    this.dato = d;
    return this.dato;
  }
}
let a: Caja = new Caja();
let b: Caja = new Caja();
a.guardar(1);
b.guardar(2);
print(a.dato * 10 + b.dato);
