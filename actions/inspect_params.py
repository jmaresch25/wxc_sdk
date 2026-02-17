import ast
import os

for root, _, files in os.walk("."):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8") as file:
                tree = ast.parse(file.read(), filename=path)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    args = [a.arg for a in node.args.args]
                    print(f"{path}:{node.name}({', '.join(args)})")
