// expect: 24
// expect: 2
// expect: 9
let xs: integer[] = [1, 2, 3];
xs[1] = 20;
print(xs[0] + xs[1] + xs[2]);
let m: integer[][] = [[1, 2], [3, 4]];
m[1][0] = 9;
print(m[0][1]);
print(m[1][0]);
