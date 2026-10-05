// expect: 120
// expect: 55
function factorial(n: integer): integer {
  if (n <= 1) {
    return 1;
  }
  return n * factorial(n - 1);
}
function fib(n: integer): integer {
  if (n < 2) {
    return n;
  }
  return fib(n - 1) + fib(n - 2);
}
print(factorial(5));
print(fib(10));
