// expect: 11
// expect: 13
// expect: 21
// expect: 23
for (let i: integer = 1; i <= 2; i = i + 1) {
  for (let j: integer = 1; j <= 3; j = j + 1) {
    if (j == 2) {
      continue;
    }
    print(i * 10 + j);
  }
}
