// expect: 15
let xs: integer[] = [4, 5, 6];
let total: integer = 0;
foreach (v in xs) {
  total = total + v;
}
print(total);
