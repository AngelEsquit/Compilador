// Rubrica: funciones
// expect: 7
function id(x: integer): integer {
  return x;
}
print(id(id(id(id(7)))));
