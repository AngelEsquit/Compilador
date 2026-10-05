// expect: 1
// expect: 3
// expect: 4
let xs: integer[] = [1, 2, 3, 4, 5];
foreach (v in xs) {
  if (v == 2) {
    continue;
  }
  if (v == 5) {
    break;
  }
  print(v);
}
