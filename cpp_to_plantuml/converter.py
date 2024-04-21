import dataclasses
import pathlib
import re
import typing

from clang import cindex

from cpp_to_plantuml.objects import CppClass, CppMethod, CppField, CppVar, AccessSpecifier
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
        {cindex.CursorKind.CLASS_DECL, cindex.CursorKind.STRUCT_DECL, cindex.CursorKind.CLASS_TEMPLATE}
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

        cls = CppClass(cursor.displayname)
        self.classes[cursor.displayname] = cls

        node: cindex.Cursor
        for node in cursor.get_children():
            if node.kind in self.CLASS_KINDS:
                self._parse_class(node)
            elif node.kind == cindex.CursorKind.CXX_BASE_SPECIFIER:
                cls.base_classes.append(node.spelling)
            elif node.kind in self.VAR_KINDS:
                cls.fields.append(self._parse_field(node))
            elif node.kind in self.METHOD_KINDS:
                if node.is_deleted_method():
                    continue
                cls.methods.append(self._parse_method(node))

    @classmethod
    def _parse_field(cls, cursor: cindex.Cursor) -> CppField:
        if cursor.kind not in cls.VAR_KINDS:
            raise ValueError('Cursor is not a field')

        tokens = [i.spelling for i in cursor.get_tokens()]
        if cursor.type.spelling == 'int' and tokens[0] != 'int':
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
        var = CppVar(cursor.displayname, type_)
        return CppField(var, AccessSpecifier.from_clang(cursor.access_specifier), 'static' in tokens)

    @classmethod
    def _parse_method(cls, cursor: cindex.Cursor) -> CppMethod:
        if cursor.kind not in cls.METHOD_KINDS:
            raise ValueError('Cursor is not a method')

        method = CppMethod(cursor.spelling, cursor.result_type.spelling,
                           AccessSpecifier.from_clang(cursor.access_specifier),
                           is_abstract=cursor.is_pure_virtual_method(),
                           is_static=cursor.is_static_method())
        for arg in cursor.get_arguments():
            method.args.append(CppVar(arg.spelling, arg.type.spelling))
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
                    f.write(f'{cls.pure_name} --|> {base.partition("<")[0]}\n')
                    printed_bases = True
            if printed_bases:
                f.write('\n')

            printed_aggregations = False
            for cls in self.classes.values():
                for other_cls in self.classes.values():
                    match = False
                    for field in cls.fields:
                        if re.search(rf'\b{other_cls.pure_name}\b', field.type):
                            f.write(f'{other_cls.pure_name} *-- {cls.pure_name}\n')
                            printed_aggregations = True
                            match = True
                            break
            if printed_aggregations:
                f.write('\n')
                            
            printed_dependencies = False
            for cls in self.classes.values():
                for other_cls in self.classes.values():
                    for method in cls.methods:
                        if re.search(rf'\b{other_cls.pure_name}\b', method.return_type) or \
                                re.search(rf'\b{other_cls.pure_name}\b', ' '.join(arg.type for arg in method.args)):
                            f.write(f'{other_cls.pure_name} <.. {cls.pure_name}\n')
                            printed_dependencies = True
                            break
            if printed_dependencies:
                f.write('\n')

            f.write('@enduml\n')