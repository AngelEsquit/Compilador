// Rubrica: recursividad
// expect: 120
class M {
  function fact(n: integer): integer {
    if (n <= 1) {
      return 1;
    }
    return n * this.fact(n - 1);
  }
}
let m: M = new M();
print(m.fact(5));
