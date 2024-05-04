import dataclasses
import pathlib
import re
import typing
import warnings

from clang import cindex

from cpp_to_plantuml.objects import CppClass, CppMethod, CppField, CppVar, AccessSpecifier, CppEnum
from cpp_to_plantuml.writers import AbstractWriter, PlantUmlWriter


@dataclasses.dataclass
class Settings:
    title: typing.Optional[str] = None
    icons_access_modifiers: bool = False
    class_writer: AbstractWriter = dataclasses.field(default_factory=PlantUmlWriter)


class Converter:
    filename: pathlib.Path
    # translation unit
    tu: cindex.TranslationUnit
    classes: dict[str, CppClass]

    CLASS_KINDS: set[cindex.CursorKind] = \
        {cindex.CursorKind.CLASS_DECL, cindex.CursorKind.STRUCT_DECL, cindex.CursorKind.CLASS_TEMPLATE,
         cindex.CursorKind.ENUM_DECL}
    METHOD_KINDS: set[cindex.CursorKind] = \
        {cindex.CursorKind.CXX_METHOD, cindex.CursorKind.FUNCTION_TEMPLATE, cindex.CursorKind.CONSTRUCTOR,
         cindex.CursorKind.FUNCTION_DECL}
    VAR_KINDS: set[cindex.CursorKind] = {cindex.CursorKind.FIELD_DECL, cindex.CursorKind.VAR_DECL}

    @staticmethod
    def _parse_file(filename: pathlib.Path, cpp_version: str) -> cindex.TranslationUnit:
        index = cindex.Index.create()
        return index.parse(filename, args=[f'-std={cpp_version}'])

    def __init__(self, filename: pathlib.Path, cpp_version: str = 'c++17'):
        if not filename.is_file():
            print(f"File {filename.absolute()} not found.")
            exit(1)

        self.filename = filename
        self.tu = self._parse_file(filename, cpp_version)
        self.classes = {}

    def translate(self, output: pathlib.Path, settings: Settings):
        self.parse_classes()
        self.output(output, settings)

    def parse_classes(self):
        cursor: cindex.Cursor = self.tu.cursor
        node: cindex.Cursor
        for node in cursor.get_children():
            if node.location.file.name != str(self.filename):
                continue
            if node.kind in self.CLASS_KINDS and node.is_definition():
                self._parse_class(node)

    def _parse_class(self, cursor: cindex.Cursor):
        if cursor.kind not in self.CLASS_KINDS:
            raise ValueError('Cursor is not a class')

        if cursor.kind == cindex.CursorKind.ENUM_DECL:
            self.classes[cursor.displayname] = CppEnum(cursor.displayname)
            return
        if cursor.displayname != cursor.spelling and \
                any(name.partition('<')[0] == cursor.spelling for name in self.classes):
            return
        cls = CppClass(cursor.displayname)
        self.classes[cursor.displayname] = cls

        node: cindex.Cursor
        for node in cursor.get_children():
            if node.kind in self.CLASS_KINDS:
                self._parse_class(node)
            elif node.kind == cindex.CursorKind.CXX_BASE_SPECIFIER:
                cls.base_classes.append(node.displayname.rpartition('::')[2])
            elif node.kind in self.VAR_KINDS:
                cls.fields.append(self._parse_field(node))
            elif node.kind in self.METHOD_KINDS:
                if node.is_deleted_method():
                    continue
                cls.methods.append(self._parse_method(node))

    @staticmethod
    def _parse_var_type(cursor: cindex.Cursor) -> str:
        exclude: re.Pattern = re.compile(r'static|\[\[.*?]]|const(?:expr|eval|init)')
        tokens = [i.spelling for i in cursor.get_tokens() if not exclude.fullmatch(i.spelling)]
        if cursor.type.spelling in ('int', 'const int') and tokens[0] != 'int':
            assign_index = tokens.index('=') if '=' in tokens else len(tokens)
            right_angle_index = (len(tokens) - 1 - tokens[:assign_index][::-1].index('>')) if '>' in tokens else -1
            name_index = tokens.index(cursor.displayname, right_angle_index + 1, assign_index)
            type_ = tokens[0]
            for t in tokens[1:name_index]:
                if type_[-1].isalnum() and t[0].isalnum():
                    type_ += ' '
                type_ += t
        else:
            type_ = cursor.type.spelling
        return type_.rpartition('::')[2]

    @classmethod
    def _parse_function_type(cls, cursor: cindex.Cursor) -> str:
        if cursor.kind not in cls.METHOD_KINDS:
            raise ValueError('Cursor is not a function')

        exclude: re.Pattern = re.compile(r'static|virtual|explicit|inline|friend|\[\[.*?]]|const(?:expr|eval|init)')
        tokens = [i.spelling for i in cursor.get_tokens() if not exclude.fullmatch(i.spelling)]
        if cursor.result_type.spelling == 'int' and tokens[0] != 'int':
            name_index = tokens.index('(') - 1
            if name_index <= 0:
                warnings.warn(f"Error. Can not detect type of function {cursor.displayname}. Returned int as default.")
                return 'int'
            type_ = tokens[0]
            for t in tokens[1:name_index]:
                if type_[-1].isalnum() and t[0].isalnum():
                    type_ += ' '
                type_ += t
        else:
            type_ = cursor.result_type.spelling
        return type_.rpartition('::')[2]

    @classmethod
    def _parse_field(cls, cursor: cindex.Cursor) -> CppField:
        if cursor.kind not in cls.VAR_KINDS:
            raise ValueError('Cursor is not a field')

        var = CppVar(cursor.displayname, cls._parse_var_type(cursor))
        return CppField(var, AccessSpecifier.from_clang(cursor.access_specifier),
                        'static' in (i.spelling for i in cursor.get_tokens()))

    @classmethod
    def _is_method_abstract(cls, cursor: cindex.Cursor) -> bool:
        if cursor.kind not in cls.METHOD_KINDS:
            raise ValueError('Cursor is not a method')
        tokens = [i.spelling for i in cursor.get_tokens()]
        return tokens[-2:] == ['=', '0']

    @classmethod
    def _parse_method(cls, cursor: cindex.Cursor) -> CppMethod:
        if cursor.kind not in cls.METHOD_KINDS:
            raise ValueError('Cursor is not a method')

        if cursor.kind == cindex.CursorKind.CONSTRUCTOR:
            method = CppMethod(cursor.spelling, 'void',
                               AccessSpecifier.from_clang(cursor.access_specifier),
                               is_constructor=True)
        else:
            method = CppMethod(cursor.spelling, cls._parse_function_type(cursor),
                               AccessSpecifier.from_clang(cursor.access_specifier),
                               is_abstract=cls._is_method_abstract(cursor),
                               is_static=cursor.is_static_method())
        for arg in cursor.get_arguments():
            method.args.append(CppVar(arg.displayname, cls._parse_var_type(arg)))
        return method

    def output(self, output: pathlib.Path, settings: Settings):
        with open(output, 'w') as f:
            f.write('@startuml\n\n')
            if settings.title:
                f.write(f'title {settings.title}\n\n')
            if not settings.icons_access_modifiers:
                f.write('skinparam classAttributeIconSize 0\n\n')

            for cls in self.classes.values():
                f.write(settings.class_writer.write(cls) + '\n\n')

            printed_bases = False
            for cls in self.classes.values():
                for base in cls.base_classes:
                    base_is_interface = False
                    if base in self.classes and self.classes[base].is_interface:
                        base_is_interface = True
                    f.write(f'{cls.pure_name} {"..|>" if base_is_interface else "--|>"} {base.partition("<")[0]}\n')
                    printed_bases = True
            if printed_bases:
                f.write('\n')

            aggregations: set[tuple[str, str]] = set()
            printed_aggregations = False
            for cls in self.classes.values():
                for other_cls in self.classes.values():
                    for field in cls.fields:
                        if re.search(rf'\b{other_cls.pure_name}\b', field.type):
                            f.write(f'{other_cls.pure_name} *-- {cls.pure_name}\n')
                            aggregations.add((cls.pure_name, other_cls.pure_name))
                            printed_aggregations = True
                            break
            if printed_aggregations:
                f.write('\n')

            dependencies: set[tuple[str, str]] = set()
            printed_dependencies = False
            for cls in self.classes.values():
                for other_cls in self.classes.values():
                    if cls == other_cls or \
                            other_cls.name in cls.base_classes or \
                            (cls.pure_name, other_cls.pure_name) in aggregations or \
                            any((self.classes[base].pure_name, other_cls.pure_name) in dependencies
                                for base in cls.base_classes
                                if base in self.classes):
                        continue
                    for method in cls.methods:
                        if re.search(rf'\b{other_cls.pure_name}\b', method.return_type) or \
                                re.search(rf'\b{other_cls.pure_name}\b', ' '.join(arg.type for arg in method.args)):
                            f.write(f'{other_cls.pure_name} <.. {cls.pure_name}\n')
                            dependencies.add((cls.pure_name, other_cls.pure_name))
                            printed_dependencies = True
                            break
            if printed_dependencies:
                f.write('\n')

            f.write('@enduml\n')
