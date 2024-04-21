import argparse
import pathlib

from cpp_to_plantuml import Converter, Settings
from cpp_to_plantuml.writers import PlantUmlWriter


def main():
    arg_parser = argparse.ArgumentParser(description="Produces a PlantUML class diagram from a C++ source code.")
    arg_parser.add_argument('source', help="a path to a source code", type=pathlib.Path)
    arg_parser.add_argument('-o', '--out', metavar='path', help="An output file.",
                            default='out.puml', type=pathlib.Path)
    arg_parser.add_argument('--std', metavar='version', help="A version of C++ standard to use (e.g. \"c++20\").",
                            default='c++17')
    arg_parser.add_argument('-f', '--force', action='store_true', help="Force overwrite the output file.")
    arg_parser.add_argument('--title', metavar='text', help="A title for your UML.", type=str)
    arg_parser.add_argument('--cstyle', action='store_true', help="Render a variable's type after its name.")
    arg_parser.add_argument('--icons', action='store_true',
                            help="Enable icons instead of characters for access specifiers.")
    args = arg_parser.parse_args()

    out: pathlib.Path = args.out
    if out.is_dir():
        print(f"{out.absolute()} is a directory.")
        exit(1)
    if out.is_file() and not args.force:
        print(f"{out.absolute()} already exists. Use -f to overwrite.")
        exit(1)
    converter = Converter(args.source, cpp_version=args.std)
    converter.translate(out,
                        Settings(
                            title=args.title,
                            class_writer=PlantUmlWriter(not args.cstyle),
                            icons_access_modifiers=args.icons,
                        ))


if __name__ == '__main__':
    main()
