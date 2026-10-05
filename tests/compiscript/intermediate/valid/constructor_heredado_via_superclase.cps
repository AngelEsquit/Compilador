// expect: 4
// expect: 4
// expect: true
class Base {
  let n: integer;

  function constructor(n: integer) {
    this.n = n;
  }
}
class Derivada : Base {}

let b: Base = new Derivada(4);
print(b.n);
let d: Derivada = new Derivada(4);
print(d.n);
print(b.n == d.n);
