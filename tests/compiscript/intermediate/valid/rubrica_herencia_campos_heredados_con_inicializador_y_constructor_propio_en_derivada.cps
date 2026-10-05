// Rubrica: herencia
// expect: 5
// expect: 2
class A {
  let x: integer = 5;
}
class B : A {
  let y: integer = 1;
  function constructor() {
    this.y = 2;
  }
}
let b: B = new B();
print(b.x);
print(b.y);
