# CppToPlantUML
A simple script that generates a PlantUML class diagram from a C++ source file

## Installation

1. Install [Python 3.11+](https://www.python.org/downloads/release/python-3117/)
2. Install [Poetry](https://python-poetry.org/docs/)
3. Clone the repository and enter the directory.
```bash
git clone https://github.com/Makcal/CppToPlantUML.git
cd CppToPlantUML
```
4. Install dependencies.
```bash
poetry install --no-root
```
Done!

## Usage

Produces a PlantUML class diagram from a C++ source file to `out.puml` by default.

```bash
poetry run python src/main.py <source.cpp>
```

You can enjoy and download your diagram for example with [PlantText](https://www.planttext.com/).

### Help

Read help for options and more information:

```bash
poetry run python src/main.py --help
```
