// Rubrica: herencia
// expect: 2
class A {
  let c: integer = 0;
}
class B : A {
  function inc(): integer {
    this.c = this.c + 1;
    return this.c;
  }
}
let b: B = new B();
b.inc();
print(b.inc());
