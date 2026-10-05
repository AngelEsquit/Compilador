// Rubrica: herencia
// expect: hola B
class A {
  function nombre(): string {
    return "A";
  }
  function saludar(): string {
    return "hola " + this.nombre();
  }
}
class B : A {
  function nombre(): string {
    return "B";
  }
}
let b: B = new B();
let a: A = b;
print(a.saludar());
