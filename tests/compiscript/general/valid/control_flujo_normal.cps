function clasificar(n: integer): string {
  if (n > 0) {
    return "positivo";
  }
  return "no positivo";
}

function suma(a: integer, b: integer): integer {
  return a + b;
}

let total: integer = suma(2, 3);
print(clasificar(total));

let notas: integer[] = [90, 85, 100];
foreach (n in notas) {
  if (n < 60) { continue; }
  if (n == 100) { break; }
  print(n);
}
