// expect: 10
function f(xs: integer[]): integer {
  let s: integer = 0;
  function acc(n: integer): integer {
    s = s + n;
    return s;
  }
  foreach (v in xs) {
    acc(v);
  }
  return s;
}
print(f([1, 2, 3, 4]));
