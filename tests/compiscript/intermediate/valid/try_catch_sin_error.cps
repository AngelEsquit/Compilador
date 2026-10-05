// expect: dentro
// expect: fuera
try {
  print("dentro");
} catch (e) {
  print("no se ejecuta");
}
print("fuera");
