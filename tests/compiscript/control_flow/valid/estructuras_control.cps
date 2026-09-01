let count: integer = 0;

if (count == 0) {
  count = 1;
} else {
  count = 2;
}

while (count < 5) {
  count = count + 1;
  if (count == 3) {
    continue;
  }
  if (count == 4) {
    break;
  }
}

do {
  count = count - 1;
} while (count > 0);

for (let i: integer = 0; i < 3; i = i + 1) {
  count = count + i;
}
