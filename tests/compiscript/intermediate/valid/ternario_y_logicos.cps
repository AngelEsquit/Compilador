// expect: 3
// expect: 8
// expect: true
// expect: true
// expect: false
let a: integer = 3;
let b: integer = 8;
print(a < b ? a : b);
print(a > b ? a : b);
print(a < b && b < 10);
print(a > b || b == 8);
print(!(a == 3));
