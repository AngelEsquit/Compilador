// Rubrica: control
// expect: 1
// expect: tres
// expect: 3
// expect: 4
let i: integer = 0;
while (i < 4) {
  i = i + 1;
  switch (i) {
    case 2: continue;
    case 3: print("tres");
  }
  print(i);
}
