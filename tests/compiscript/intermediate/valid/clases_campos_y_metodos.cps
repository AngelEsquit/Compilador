// expect: 15
// expect: 18
// expect: 18
// expect: 1
class Contador {
  let valor: integer = 10;

  function constructor(inicio: integer) {
    this.valor = this.valor + inicio;
  }

  function sumar(n: integer): integer {
    this.valor = this.valor + n;
    return this.valor;
  }
}
let c: Contador = new Contador(5);
print(c.valor);
print(c.sumar(3));
print(c.valor);
c.valor = 0;
print(c.sumar(1));
