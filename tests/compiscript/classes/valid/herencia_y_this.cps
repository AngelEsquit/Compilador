class Animal {
  let nombre: string;

  function constructor(nombre: string) {
    this.nombre = nombre;
  }

  function hablar(): string {
    return this.nombre + " hace ruido.";
  }
}

class Perro : Animal {
  function ladrar(): string {
    return this.nombre + " ladra.";
  }
}

class Cachorro : Perro {}

let c: Cachorro = new Cachorro("Toby");
print(c.hablar());
print(c.ladrar());
print(c.nombre);
