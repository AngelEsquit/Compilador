function suma(a: integer, b: integer): integer {
  return a + b;
}

function saludar(nombre: string): string {
  return "Hola " + nombre;
}

function anunciar(mensaje: string) {
  print(mensaje);
  return;
}

let total: integer = suma(2, 3);
let saludo: string = saludar("Compiscript");
anunciar(saludo);
print(total);
