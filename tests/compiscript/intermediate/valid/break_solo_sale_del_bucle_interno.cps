// expect: 1
// expect: 2
// expect: 3
for (let i: integer = 0; i < 3; i = i + 1) {
  let j: integer = 0;
  while (true) {
    j = j + 1;
    if (j > i) {
      break;
    }
  }
  print(j);
}
