// Rubrica: clases
// expect: 20
class C {
  let v: integer = 2;
  function a(): integer {
    return this.v;
  }
  function b(): integer {
    return this.a() * 10;
  }
}
let c: C = new C();
print(c.b());
