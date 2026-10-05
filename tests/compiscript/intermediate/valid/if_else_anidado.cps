// expect: -1
// expect: 0
// expect: 1
function clasificar(n: integer): integer {
  if (n < 0) {
    return -1;
  } else {
    if (n == 0) {
      return 0;
    } else {
      return 1;
    }
  }
}
print(clasificar(-5));
print(clasificar(0));
print(clasificar(9));
