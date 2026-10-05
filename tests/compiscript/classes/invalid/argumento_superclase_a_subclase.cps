class Animal {}
class Perro : Animal {}

function adoptar(p: Perro): string {
  return "ok";
}

// la funcion pide una subclase y recibe la superclase
print(adoptar(new Animal()));
