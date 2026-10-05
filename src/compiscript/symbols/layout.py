"""Distribucion de memoria: registros de activacion, area estatica y layout de clases.

Se calcula sobre el arbol de ambitos que deja el analisis semantico y completa
la tabla de simbolos (`storage`, `offset`, `size`, `frame`) con la informacion
que necesitara un generador de assembler.

Registro de activacion (offsets en bytes respecto a `fp`, crecen hacia arriba):

    fp+0   saved_fp         enlace dinamico (fp del llamador)
    fp+8   return_address   direccion de retorno
    fp+16  access_link      enlace estatico (fp de la funcion que encierra lexicamente)
    fp+24  parametros       (`this` primero en metodos)
           variables locales (los bloques hermanos comparten espacio)
           temporales        (8 bytes cada uno, los reporta el generador de TAC)

Las variables globales viven en un area estatica (`global`). El codigo de nivel
superior tambien tiene un registro, `main`, para sus temporales y para las
variables declaradas dentro de bloques o bucles de nivel superior.

Objetos: 8 bytes de cabecera (puntero a la clase) y despues los campos; los
campos heredados conservan su offset en las subclases.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from compiscript.symbols.scope import Scope, ScopeKind
from compiscript.symbols.symbol import (
    ClassSymbol,
    ConstSymbol,
    ParameterSymbol,
    Symbol,
    VariableSymbol,
)
from compiscript.typesystem.types import BooleanType, IntegerType, Type

WORD = 8
CONTROL_AREA: tuple[tuple[str, int, int], ...] = (
    ("saved_fp", 0, WORD),
    ("return_address", 8, WORD),
    ("access_link", 16, WORD),
)
CONTROL_SIZE = 24
OBJECT_HEADER = WORD
TEMP_SIZE = WORD

_STORABLE = (VariableSymbol, ConstSymbol, ParameterSymbol)


def size_of(decl_type: Type) -> int:
    """Tamano en bytes: integer 4, boolean 1; float y toda referencia (string, arreglo, objeto) 8."""
    if isinstance(decl_type, IntegerType):
        return 4
    if isinstance(decl_type, BooleanType):
        return 1
    return WORD


def _align(offset: int, size: int) -> int:
    return (offset + size - 1) // size * size


@dataclass
class Slot:
    """Una posicion con nombre dentro de un registro, del area estatica o de un objeto."""

    name: str
    type_name: str
    kind: str
    offset: int
    size: int

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type_name,
            "kind": self.kind,
            "offset": self.offset,
            "size": self.size,
        }


@dataclass
class ActivationRecord:
    """Registro de activacion de una funcion, metodo o del codigo de nivel superior."""

    name: str
    kind: str  # main | function | method | constructor
    parent: Optional[str]
    level: int
    params: list[Slot] = field(default_factory=list)
    locals: list[Slot] = field(default_factory=list)
    locals_end: int = CONTROL_SIZE
    temp_count: int = 0

    @property
    def temps_offset(self) -> int:
        return _align(self.locals_end, WORD)

    @property
    def frame_size(self) -> int:
        return _align(self.temps_offset + self.temp_count * TEMP_SIZE, WORD)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "parent": self.parent,
            "level": self.level,
            "control": [{"name": n, "offset": o, "size": s} for n, o, s in CONTROL_AREA],
            "params": [slot.to_dict() for slot in self.params],
            "locals": [slot.to_dict() for slot in self.locals],
            "temps": {"count": self.temp_count, "offset": self.temps_offset, "size": TEMP_SIZE},
            "frameSize": self.frame_size,
        }


@dataclass
class ClassLayout:
    """Layout de instancias y tabla de metodos de una clase."""

    name: str
    superclass: Optional[str]
    fields: list[Slot] = field(default_factory=list)
    size: int = OBJECT_HEADER
    methods: list[dict] = field(default_factory=list)  # {name, label, slot}

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "superclass": self.superclass,
            "size": self.size,
            "fields": [slot.to_dict() for slot in self.fields],
            "methods": list(self.methods),
        }


@dataclass
class Layout:
    data_size: int = 0
    data_symbols: list[Slot] = field(default_factory=list)
    records: dict[str, ActivationRecord] = field(default_factory=dict)
    classes: dict[str, ClassLayout] = field(default_factory=dict)

    def apply_temps(self, temp_counts: dict[str, int]) -> None:
        """Registra cuantos temporales uso cada funcion en el TAC y crea los registros sinteticos."""
        for name, count in temp_counts.items():
            record = self.records.get(name)
            if record is None:
                # Constructor sintetizado por el generador para inicializar campos.
                owner = name.rsplit(".", 1)[0] if "." in name else None
                record = ActivationRecord(name, "constructor" if owner else "function", None, 1)
                if owner:
                    record.params.append(Slot("this", owner, "param", CONTROL_SIZE, WORD))
                    record.locals_end = CONTROL_SIZE + WORD
                self.records[name] = record
            record.temp_count = count

    def to_dict(self) -> dict:
        return {
            "dataArea": {"size": self.data_size, "symbols": [s.to_dict() for s in self.data_symbols]},
            "records": [record.to_dict() for record in self.records.values()],
            "classes": [cls.to_dict() for cls in self.classes.values()],
        }

    def to_text(self) -> str:
        lines = [f"area estatica (global): {self.data_size} bytes"]
        for slot in self.data_symbols:
            lines.append(f"  global+{slot.offset:<4} {slot.name}: {slot.type_name} ({slot.size} bytes)")
        for record in self.records.values():
            lines.append("")
            parent = f", dentro de {record.parent}" if record.parent else ""
            lines.append(f"registro de activacion {record.name} ({record.kind}, nivel {record.level}{parent})")
            for name, offset, size in CONTROL_AREA:
                lines.append(f"  fp+{offset:<4} {name} ({size} bytes)")
            for slot in record.params + record.locals:
                lines.append(
                    f"  fp+{slot.offset:<4} {slot.name}: {slot.type_name} [{slot.kind}] ({slot.size} bytes)"
                )
            if record.temp_count:
                lines.append(
                    f"  fp+{record.temps_offset:<4} temporales: {record.temp_count} x {TEMP_SIZE} bytes"
                )
            lines.append(f"  tamano del frame: {record.frame_size} bytes")
        for cls in self.classes.values():
            lines.append("")
            parent = f" : {cls.superclass}" if cls.superclass else ""
            lines.append(f"clase {cls.name}{parent} ({cls.size} bytes por instancia)")
            for slot in cls.fields:
                lines.append(f"  obj+{slot.offset:<4} {slot.name}: {slot.type_name} ({slot.size} bytes)")
            for method in cls.methods:
                lines.append(f"  metodo[{method['slot']}] {method['name']} -> {method['label']}")
        return "\n".join(lines)


def _place(symbol: Symbol, cursor: int, storage: str, frame: str) -> Slot:
    """Fija la ubicacion del simbolo (alineada a su tamano) y devuelve su slot."""
    size = size_of(symbol.decl_type)
    offset = _align(cursor, size)
    symbol.storage = storage
    symbol.offset = offset
    symbol.size = size
    symbol.frame = frame
    return Slot(symbol.name, symbol.decl_type.name, storage, offset, size)


class _Builder:
    def __init__(self) -> None:
        self.layout = Layout()
        self._class_scopes: dict[str, Scope] = {}
        self._in_progress: set[str] = set()

    def build(self, global_scope: Scope) -> Layout:
        main = ActivationRecord("main", "main", None, 0)
        self.layout.records["main"] = main

        cursor = 0
        for symbol in global_scope.symbols():
            if isinstance(symbol, _STORABLE):
                slot = _place(symbol, cursor, "global", "global")
                self.layout.data_symbols.append(slot)
                cursor = slot.offset + slot.size
        self.layout.data_size = _align(cursor, WORD)

        main.locals_end = self._children(global_scope, main, CONTROL_SIZE)
        for name, scope in self._class_scopes.items():
            self._class_layout(name, scope)
        return self.layout

    def _children(self, scope: Scope, record: ActivationRecord, cursor: int) -> int:
        """Reparte los hijos de `scope`; los bloques hermanos reutilizan el mismo espacio."""
        peak = cursor
        for child in scope.children:
            if child.kind is ScopeKind.FUNCTION:
                self._function(child, record, None)
            elif child.kind is ScopeKind.CLASS:
                self._class_scopes[child.name] = child
                for method_scope in child.children:
                    if method_scope.kind is ScopeKind.FUNCTION:
                        self._function(method_scope, record, child.name)
            else:
                peak = max(peak, self._block(child, record, cursor))
        return peak

    def _block(self, scope: Scope, record: ActivationRecord, cursor: int) -> int:
        for symbol in scope.symbols():
            if isinstance(symbol, _STORABLE):
                slot = _place(symbol, cursor, "local", record.name)
                record.locals.append(slot)
                cursor = slot.offset + slot.size
        return self._children(scope, record, cursor)

    def _function(self, scope: Scope, enclosing: ActivationRecord, class_name: Optional[str]) -> None:
        name = f"{class_name}.{scope.name}" if class_name else scope.name
        if class_name:
            kind = "constructor" if scope.name == "constructor" else "method"
        else:
            kind = "function"
        record = ActivationRecord(name, kind, enclosing.name, enclosing.level + 1)
        cursor = CONTROL_SIZE
        if class_name:
            record.params.append(Slot("this", class_name, "param", cursor, WORD))
            cursor += WORD
        for symbol in scope.symbols():
            if isinstance(symbol, ParameterSymbol):
                slot = _place(symbol, cursor, "param", name)
                record.params.append(slot)
                cursor = slot.offset + slot.size
        record.locals_end = cursor
        # Un nombre repetido (funciones anidadas homonimas) conserva el primer registro.
        self.layout.records.setdefault(name, record)
        record.locals_end = self._children(scope, record, cursor)

    def _class_layout(self, name: str, scope: Scope) -> Optional[ClassLayout]:
        existing = self.layout.classes.get(name)
        if existing is not None:
            return existing
        class_symbol = scope.parent.resolve_local(name) if scope.parent else None
        superclass = class_symbol.superclass_name if isinstance(class_symbol, ClassSymbol) else None
        parent_layout = None
        # Un ciclo de herencia ya se reporta como error semantico; aqui solo se evita recurrir sin fin.
        self._in_progress.add(name)
        if superclass and superclass in self._class_scopes and superclass not in self._in_progress:
            parent_layout = self._class_layout(superclass, self._class_scopes[superclass])
        self._in_progress.discard(name)

        layout = ClassLayout(name, superclass if parent_layout else None)
        if parent_layout is not None:
            layout.fields = list(parent_layout.fields)
            layout.size = parent_layout.size
            layout.methods = [dict(method) for method in parent_layout.methods]
        self.layout.classes[name] = layout

        for symbol in scope.symbols():
            if isinstance(symbol, (VariableSymbol, ConstSymbol)):
                slot = _place(symbol, layout.size, "field", name)
                layout.fields.append(slot)
                layout.size = slot.offset + slot.size
        layout.size = _align(layout.size, WORD)

        for child in scope.children:
            if child.kind is not ScopeKind.FUNCTION or child.name == "constructor":
                continue
            label = f"{name}.{child.name}"
            for method in layout.methods:
                if method["name"] == child.name:
                    method["label"] = label
                    break
            else:
                layout.methods.append({"name": child.name, "label": label, "slot": len(layout.methods)})
        return layout


def compute_layout(global_scope: Scope) -> Layout:
    """Calcula registros de activacion, area estatica y layout de clases, y anota los simbolos."""
    return _Builder().build(global_scope)
