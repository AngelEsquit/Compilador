// expect: 3
function contar(): integer {
  let n: integer = 0;
  function inc(): integer {
    n = n + 1;
    return n;
  }
  inc();
  inc();
  return inc();
}
print(contar());
