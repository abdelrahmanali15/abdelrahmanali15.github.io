import ast
from typing import List, Dict, Set, Any
from pydantic import BaseModel, Field
import hashlib


class ChangeType(BaseModel):
    structural: bool = False
    minor_edit: bool = False
    rearrangement: bool = False


class FunctionChange(BaseModel):
    name: str
    signature_change: bool = False
    body_change: ChangeType = Field(default_factory=ChangeType)
    nested_function_change: bool = False


class ClassMethodChange(BaseModel):
    class_name: str
    method_name: str
    signature_change: bool = False
    body_change: ChangeType = Field(default_factory=ChangeType)


class ChangeAnalysis(BaseModel):
    added_functions: List[str] = Field(default_factory=list)
    removed_functions: List[str] = Field(default_factory=list)
    function_changes: List[FunctionChange] = Field(default_factory=list)
    class_method_changes: List[ClassMethodChange] = Field(default_factory=list)


class ASTVisitor(ast.NodeVisitor):
    def __init__(self):
        self.functions: Dict[str, ast.FunctionDef] = {}
        self.classes: Dict[str, ast.ClassDef] = {}

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.functions[node.name] = node
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.classes[node.name] = node
        self.generic_visit(node)


class ASTHasher(ast.NodeVisitor):
    def __init__(self):
        self.hash = hashlib.md5()

    def visit(self, node: ast.AST):
        self.hash.update(type(node).__name__.encode())
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        self.visit(item)
            elif isinstance(value, ast.AST):
                self.visit(value)
        return self.hash.hexdigest()


class CodeChangeAnalyzer:
    def __init__(self, old_code: str, new_code: str):
        self.old_ast = ast.parse(old_code)
        self.new_ast = ast.parse(new_code)
        self.old_visitor = ASTVisitor()
        self.new_visitor = ASTVisitor()
        self.old_visitor.visit(self.old_ast)
        self.new_visitor.visit(self.new_ast)

    def analyze_changes(self) -> ChangeAnalysis:
        changes = ChangeAnalysis()

        changes.added_functions = list(
            set(self.new_visitor.functions.keys()) - set(self.old_visitor.functions.keys()))
        changes.removed_functions = list(
            set(self.old_visitor.functions.keys()) - set(self.new_visitor.functions.keys()))

        for func_name in set(self.old_visitor.functions.keys()) & set(self.new_visitor.functions.keys()):
            function_change = self._analyze_function_change(func_name)
            changes.function_changes.append(function_change)

        changes.class_method_changes = self._analyze_class_method_changes()

        return changes

    def _analyze_function_change(self, func_name: str) -> FunctionChange:
        old_func = self.old_visitor.functions[func_name]
        new_func = self.new_visitor.functions[func_name]

        signature_change = self._has_signature_change(old_func, new_func)
        body_change = self._analyze_body_change(old_func.body, new_func.body)
        nested_function_change = self._has_nested_function_change(
            old_func, new_func)

        return FunctionChange(
            name=func_name,
            signature_change=signature_change,
            body_change=body_change,
            nested_function_change=nested_function_change
        )

    def _has_signature_change(self, old_func: ast.FunctionDef, new_func: ast.FunctionDef) -> bool:
        return not self._compare_ast_nodes(old_func.args, new_func.args)

    def _analyze_body_change(self, old_body: List[ast.stmt], new_body: List[ast.stmt]) -> ChangeType:
        old_hashes = [ASTHasher().visit(stmt) for stmt in old_body]
        new_hashes = [ASTHasher().visit(stmt) for stmt in new_body]

        if old_hashes == new_hashes:
            return ChangeType()

        change_type = ChangeType()

        old_set = set(old_hashes)
        new_set = set(new_hashes)

        if len(old_set) != len(new_set):
            change_type.structural = True
        elif old_set != new_set:
            change_type.minor_edit = True
        else:
            change_type.rearrangement = True

        return change_type

    def _has_nested_function_change(self, old_func: ast.FunctionDef, new_func: ast.FunctionDef) -> bool:
        old_nested = set(node.name for node in ast.walk(
            old_func) if isinstance(node, ast.FunctionDef) and node != old_func)
        new_nested = set(node.name for node in ast.walk(
            new_func) if isinstance(node, ast.FunctionDef) and node != new_func)
        return old_nested != new_nested

    def _analyze_class_method_changes(self) -> List[ClassMethodChange]:
        changed_methods = []

        for class_name in set(self.old_visitor.classes.keys()) & set(self.new_visitor.classes.keys()):
            old_class = self.old_visitor.classes[class_name]
            new_class = self.new_visitor.classes[class_name]

            old_methods = {node.name: node for node in ast.walk(
                old_class) if isinstance(node, ast.FunctionDef)}
            new_methods = {node.name: node for node in ast.walk(
                new_class) if isinstance(node, ast.FunctionDef)}

            for method_name in set(old_methods.keys()) & set(new_methods.keys()):
                old_method = old_methods[method_name]
                new_method = new_methods[method_name]

                signature_change = self._has_signature_change(
                    old_method, new_method)
                body_change = self._analyze_body_change(
                    old_method.body, new_method.body)

                if signature_change or body_change != ChangeType():
                    changed_methods.append(ClassMethodChange(
                        class_name=class_name,
                        method_name=method_name,
                        signature_change=signature_change,
                        body_change=body_change
                    ))

        return changed_methods

    def _compare_ast_nodes(self, node1: ast.AST, node2: ast.AST) -> bool:
        if type(node1) != type(node2):
            return False

        for field in node1._fields:
            value1 = getattr(node1, field)
            value2 = getattr(node2, field)

            if isinstance(value1, ast.AST) and isinstance(value2, ast.AST):
                if not self._compare_ast_nodes(value1, value2):
                    return False
            elif isinstance(value1, list) and isinstance(value2, list):
                if len(value1) != len(value2):
                    return False
                for item1, item2 in zip(value1, value2):
                    if isinstance(item1, ast.AST) and isinstance(item2, ast.AST):
                        if not self._compare_ast_nodes(item1, item2):
                            return False
                    elif item1 != item2:
                        return False
            elif value1 != value2:
                return False

        return True


# Example usage
old_code = """
def greet(name):
    print(f"Hello, {name}!")

class Calculator:
    def add(self, a, b):
        return a + b

def process_data(data):
    for item in data:
        print(item)
"""

new_code = """
def greet(name, greeting="Hello"):
    print(f"{greeting}, {name}!")
    print(f"{greeting}, {name}!")

class Calculator:
    def add(self, a, b):
        result = a + b
        return result

def process_data(data):
    while data:
        item = data.pop()
        print(item)

def new_function():
    pass
"""

analyzer = CodeChangeAnalyzer(old_code, new_code)
changes = analyzer.analyze_changes()

print(changes.model_dump_json(indent=2))
