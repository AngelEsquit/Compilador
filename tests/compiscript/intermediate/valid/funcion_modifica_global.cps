// expect: 2
let contador: integer = 0;
function incrementar(): integer {
  contador = contador + 1;
  return contador;
}
incrementar();
incrementar();
print(contador);
