// expect: 14
function f(): integer {
  let x: integer = 7;
  function g(): integer {
    function h(): integer {
      return x * 2;
    }
    return h();
  }
  return g();
}
print(f());
