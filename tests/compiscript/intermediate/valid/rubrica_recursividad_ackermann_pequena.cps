// Rubrica: recursividad
// expect: 9
function ack(m: integer, n: integer): integer {
  if (m == 0) {
    return n + 1;
  }
  if (n == 0) {
    return ack(m - 1, 1);
  }
  return ack(m - 1, ack(m, n - 1));
}
print(ack(2, 3));
