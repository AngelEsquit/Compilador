// expect: 12
function a(): integer {
  function inner(): integer {
    return 1;
  }
  return inner();
}
function b(): integer {
  function inner(): integer {
    return 2;
  }
  return inner();
}
print(a() * 10 + b());
