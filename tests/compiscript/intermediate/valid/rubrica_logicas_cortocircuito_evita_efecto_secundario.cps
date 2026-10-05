// Rubrica: logicas
// expect: 0
let n: integer = 0;
function tocar(): boolean {
  n = n + 1;
  return true;
}
let r: boolean = false && tocar();
print(n);
