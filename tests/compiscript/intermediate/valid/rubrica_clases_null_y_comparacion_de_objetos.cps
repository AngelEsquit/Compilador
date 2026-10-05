// Rubrica: clases
// expect: true
// expect: false
// expect: true
class A {
}
let a: A = null;
let b: A = new A();
print(a == null);
print(b == null);
print(b == b);
