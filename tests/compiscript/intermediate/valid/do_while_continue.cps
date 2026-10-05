// expect: 3
// expect: 3
let i: integer = 0;
let suma: integer = 0;
do {
  i = i + 1;
  if (i == 3) {
    continue;
  }
  suma = suma + i;
} while (i < 3);
print(suma);
print(i);
