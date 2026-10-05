// Rubrica: trycatch (errores de ejecucion)
// expect: 1
// expect: 3
// expect: 4
let i: integer = 0;
while (i < 10) {
  i = i + 1;
  try {
    if (i == 2) {
      continue;
    }
    if (i == 5) {
      break;
    }
    print(i);
  } catch (e) {
    print("no");
  }
}
