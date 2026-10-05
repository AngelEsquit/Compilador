// Rubrica: trycatch (errores de ejecucion)
// expect: 1
// expect: 2
// expect: 3
try {
  print(1);
} catch (e) {
  print("no");
}
print(2);
try {
  print(3);
} catch (e) {
  print("no");
}
