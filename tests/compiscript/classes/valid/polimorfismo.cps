class Animal {
  function hablar(): string {
    return "...";
  }
}

class Perro : Animal {
  function hablar(): string {
    return "guau";
  }
}

class Cachorro : Perro {}

function presentar(a: Animal): string {
  return a.hablar();
}

function crear(): Animal {
  return new Cachorro();
}

let a: Animal = new Perro();
a = new Cachorro();
let zoo: Animal[] = [new Perro(), new Animal()];
let mismo: boolean = a == zoo[0];
let elegido: Animal = mismo ? new Perro() : new Animal();
let nada: Animal = null;
print(presentar(new Perro()));
