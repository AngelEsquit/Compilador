// expect: 12
function suma(n: integer): integer {
  let k: integer = 2;
  function rec(m: integer): integer {
    if (m <= 0) {
      return 0;
    }
    return m * k + rec(m - 1);
  }
  return rec(n);
}
print(suma(3));
