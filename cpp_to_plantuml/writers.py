from abc import ABC, abstractmethod

from cpp_to_plantuml.objects import CppClass, CppVar


class AbstractWriter(ABC):
    @abstractmethod
    def write(self, class_: CppClass) -> str:
        pass


class PlantUmlWriter(AbstractWriter):
    postfix_style: bool

    def __init__(self, postfix_style=True):
        """
        :param postfix_style: If True, the type of variables will be written after the variable name.
        C-style, otherwise.
        """
        self.postfix_style = postfix_style

    def var_to_string(self, var: CppVar) -> str:
        return f'{var.name}: {var.type}' if self.postfix_style else f'{var.type} {var.name}'

    def write(self, class_: CppClass) -> str:
        if class_.is_interface:
            res = "interface %s {\n" % class_.name
        else:
            res = "%sclass %s {\n" % ('abstract ' if class_.is_abstract else '', class_.name)

        for field in class_.fields:
            res += (f"\t{field.access_specifier.symbol} " + ('{static} ' if field.is_static else '') +
                    f"{self.var_to_string(field.var)}\n")

        if class_.fields and class_.methods:
            res += '\n'
        for method in class_.methods:
            values = {
                'access': method.access_specifier.symbol,
                'name': method.name,
                'return_type': method.return_type,
                'args': ', '.join(map(self.var_to_string, method.args)),
                'static': '{static} ' if method.is_static else '',
                'abstract': '{abstract} ' if method.is_abstract else ''
            }
            res += (("\t{access} {static}{abstract}{name}({args}): {return_type}\n"
                     if self.postfix_style
                     else "\t{access} {static}{abstract}{return_type} {name}({args})\n")
                    .format(**values))

        if not class_.fields and not class_.methods:
            res += "\n"

        res += "}"
        return res
