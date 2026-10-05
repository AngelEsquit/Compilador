// Rubrica: herencia
// expect: 6
class A {
  function f(): integer {
    return 1;
  }
}
class B : A {
  function g(): integer {
    return 2;
  }
}
class C : B {
  function h(): integer {
    return 3;
  }
}
let c: C = new C();
print(c.f() + c.g() + c.h());
