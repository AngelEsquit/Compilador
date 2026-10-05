// expect: dos
// expect: tres
// expect: otro
// expect: otro
function describir(x: integer): integer {
  switch (x) {
    case 1:
      print("uno");
    case 2:
      print("dos");
    case 3:
      print("tres");
    default:
      print("otro");
  }
  return x;
}
describir(2);
describir(9);
