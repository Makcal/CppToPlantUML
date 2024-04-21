import dataclasses
from enum import Enum
from functools import cached_property

from clang import cindex


class AccessSpecifier(Enum):
    def __init__(self, name: str, symbol: str):
        self.keyword = name
        self.symbol = symbol

    PUBLIC = ('public', '+')
    PROTECTED = ('protected', '#')
    PRIVATE = ('private', '-')

    keyword: str
    symbol: str

    @classmethod
    def from_clang(cls, access_specifier: cindex.AccessSpecifier):
        return {
            cindex.AccessSpecifier.PUBLIC: cls.PUBLIC,
            cindex.AccessSpecifier.PROTECTED: cls.PROTECTED,
            cindex.AccessSpecifier.PRIVATE: cls.PRIVATE
        }[access_specifier]


@dataclasses.dataclass
class CppVar:
    name: str
    type: str

    def __str__(self):
        return f'{self.name}: {self.type}'


@dataclasses.dataclass
class CppField:
    var: CppVar
    access_specifier: AccessSpecifier
    is_static: bool = False

    @property
    def name(self):
        return self.var.name

    @property
    def type(self):
        return self.var.type

    def __str__(self):
        return f'{self.access_specifier} {"static " if self.is_static else ""}field {self.var.name}: {self.var.type}'


@dataclasses.dataclass
class CppMethod:
    name: str
    return_type: str
    access_specifier: AccessSpecifier
    args: list[CppVar] = dataclasses.field(default_factory=list)
    is_static: bool = False
    is_abstract: bool = False
    is_constructor: bool = False

    def __str__(self):
        return (f'{self.access_specifier} {"static " if self.is_static else ""} '
                f'{"abstract " if self.is_abstract else ""} '
                f'{self.name}({", ".join(map(str, self.args))})'
                + ': {self.return_type}' if not self.is_constructor else '')


@dataclasses.dataclass
class CppClass:
    name: str
    base_classes: list[str] = dataclasses.field(default_factory=list)
    fields: list[CppField] = dataclasses.field(default_factory=list)
    methods: list[CppMethod] = dataclasses.field(default_factory=list)
    is_enum: bool = False

    @cached_property
    def is_abstract(self):
        return any(method.is_abstract for method in self.methods)

    @cached_property
    def is_interface(self):
        return all(method.is_abstract or method.is_static for method in self.methods) and not self.fields

    @cached_property
    def pure_name(self):
        """Returns the name of the class without template arguments."""
        return self.name.partition('<')[0]

    def __str__(self):
        sep = '\n\t'
        return (f'Class: {self.name},\n'
                f'Fields: [{sep}{sep.join(map(str, self.fields))}\n],\n'
                f'Methods: [{sep}{sep.join(map(str, self.methods))}\n],\n'
                f'Base classes: {self.base_classes}')


class CppEnum(CppClass):
    def __init__(self, name: str):
        super().__init__(name, is_enum=True)

    @property
    def is_abstract(self):
        return False

    @property
    def is_interface(self):
        return False

    def __str__(self):
        return f'Enum: {self.name}'
