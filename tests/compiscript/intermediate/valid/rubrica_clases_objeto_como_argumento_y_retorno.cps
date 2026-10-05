// Rubrica: clases
// expect: 5
// expect: 5
class P {
  let x: integer = 0;
  function constructor(x: integer) {
    this.x = x;
  }
}
function mover(p: P): P {
  p.x = p.x + 1;
  return p;
}
let p: P = new P(4);
let q: P = mover(p);
print(q.x);
print(p.x);
