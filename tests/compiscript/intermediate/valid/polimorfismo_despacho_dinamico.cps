// expect: guau
// expect: miau
// expect: animal
// expect: guau
// expect: ...
class Animal {
  function hablar(): string {
    return "...";
  }
  function presentar(): string {
    return "animal";
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

function hacerHablar(a: Animal): string {
  return a.hablar();
}

let a: Animal = new Perro();
print(a.hablar());
a = new Gato();
print(a.hablar());
print(a.presentar());
print(hacerHablar(new Perro()));
print(hacerHablar(new Animal()));
