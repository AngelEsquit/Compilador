// Rubrica: trycatch
// expect: 3
let i: integer = 0;
while (true) {
  try {
    i = i + 1;
    if (i == 3) {
      break;
    }
  } catch (e) {
    print(e);
  }
}
print(i);
