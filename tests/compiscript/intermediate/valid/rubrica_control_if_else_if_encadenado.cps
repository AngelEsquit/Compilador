// Rubrica: control
// expect: uno
// expect: dos
// expect: muchos
function f(n: integer): string {
  if (n == 1) {
    return "uno";
  } else {
    if (n == 2) {
      return "dos";
    } else {
      return "muchos";
    }
  }
}
print(f(1));
print(f(2));
print(f(9));
