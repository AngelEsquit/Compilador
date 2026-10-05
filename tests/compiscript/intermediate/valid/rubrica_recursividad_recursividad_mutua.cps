// Rubrica: recursividad
// expect: true
// expect: true
function par(n: integer): boolean {
  if (n == 0) {
    return true;
  }
  return impar(n - 1);
}
function impar(n: integer): boolean {
  if (n == 0) {
    return false;
  }
  return par(n - 1);
}
print(par(10));
print(impar(7));
