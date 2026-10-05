// Rubrica: logicas
// expect: dentro
// expect: no
let x: integer = 5;
if (x > 1 && x < 10) {
  print("dentro");
}
if (x < 1 || x > 10) {
  print("fuera");
} else {
  print("no");
}
