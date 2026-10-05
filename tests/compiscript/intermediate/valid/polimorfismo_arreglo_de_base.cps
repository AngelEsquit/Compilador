// expect: guau
// expect: miau
// expect: ...
// expect: guau
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
class Gato : Animal {
  function hablar(): string {
    return "miau";
  }
}
class Cachorro : Perro {}

let zoo: Animal[] = [new Perro(), new Gato(), new Animal(), new Cachorro()];
foreach (z in zoo) {
  print(z.hablar());
}
