// expect: guau
// expect: soy un animal
class Animal {
  function hablar(): string {
    return "...";
  }
  function presentar(): string {
    return "soy un animal";
  }
}
class Perro : Animal {
  function hablar(): string {
    return "guau";
  }
}
let p: Perro = new Perro();
print(p.hablar());
print(p.presentar());
