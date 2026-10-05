// expect: 1
// expect: 3
// expect: 5
// expect: 7
// expect: 9
let i: integer = 0;
while (i < 10) {
  i = i + 1;
  if (i % 2 == 0) {
    continue;
  }
  if (i > 7) {
    break;
  }
  print(i);
}
print(i);
