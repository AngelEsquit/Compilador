// error: SEM-SCOPE-001
function f(): integer {
  function g(): integer { return y; }
  return g();
}
