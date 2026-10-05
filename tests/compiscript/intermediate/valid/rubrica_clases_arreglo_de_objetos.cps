// Rubrica: clases
// expect: 6
class P {
  let n: integer = 0;
  function constructor(n: integer) {
    this.n = n;
  }
}
let ps: P[] = [new P(1), new P(2), new P(3)];
let t: integer = 0;
foreach (p in ps) {
  t = t + p.n;
}
print(t);
