# Parse API blueprint files to auto-generate Python code

Uses drafter (https://github.com/apiaryio/drafter) to parse APIB and create JSON representation which is then parsed 
using Pydantic models.

# 
# create yml for each apib file

    find . -iname "*.apib" -exec sh -c 'drafter -f json "$1" -o "${1%.apib}.yml"' sh {} \;

## read API blueprints as dict

## read dict

## understand the structure of the dict and parse


## Nota de alcance
Este directorio documenta el pipeline de generación de código desde API Blueprint.
Para flujos operativos de ejecución (CLI/UI, artifacts de jobs y operación v2.1), consultar:

- `Space_OdT/README.md`
