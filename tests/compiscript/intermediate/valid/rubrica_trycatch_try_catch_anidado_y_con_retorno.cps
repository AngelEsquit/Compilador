// Rubrica: trycatch
// expect: 1
function f(): integer {
  try {
    return 1;
  } catch (e) {
    return 2;
  }
}
print(f());
