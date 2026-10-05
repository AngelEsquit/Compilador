// Rubrica: herencia
// expect: hi
class A {
  let n: string;
  function constructor(n: string) {
    this.n = n;
  }
}
class B : A {
  function dec(): string {
    return this.n;
  }
}
let b: B = new B("hi");
print(b.dec());
