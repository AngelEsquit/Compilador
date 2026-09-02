function acumular(inicio: integer, paso: integer): integer {
  let actual: integer = inicio;

  function siguiente(incremento: integer): integer {
    return actual + incremento;
  }

  return siguiente(paso);
}

let resultado: integer = acumular(10, 5);
print(resultado);
