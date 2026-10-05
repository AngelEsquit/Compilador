// expect: 6
function doble(x: integer): integer {
  return x * 2;
}
function resta(a: integer, b: integer): integer {
  return a - b;
}
print(resta(doble(5), doble(2)));
