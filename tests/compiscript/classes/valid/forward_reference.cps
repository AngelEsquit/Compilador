class Persona {
  let mascota: Perro;

  function constructor(m: Perro) {
    this.mascota = m;
  }
}

class Perro {
  function ladrar(): string {
    return "guau";
  }
}

let p: Perro = new Perro();
let duenio: Persona = new Persona(p);
print(duenio.mascota.ladrar());
