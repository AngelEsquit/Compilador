// Rubrica: clases
// expect: 7
class A {
  let v: integer = 7;
}
class B {
  let a: A;
  function constructor() {
    this.a = new A();
  }
}
let b: B = new B();
print(b.a.v);
