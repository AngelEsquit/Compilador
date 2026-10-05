class Animal {}
class Perro : Animal {}
class Gato : Animal {}

// dos hermanas no son asignables entre si
let p: Perro = new Gato();
