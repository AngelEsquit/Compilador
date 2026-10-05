// expect: 15
function acumular(inicio: integer, paso: integer): integer {
  let actual: integer = inicio;

  function siguiente(incremento: integer): integer {
    return actual + incremento;
  }

  return siguiente(paso);
}
print(acumular(10, 5));
