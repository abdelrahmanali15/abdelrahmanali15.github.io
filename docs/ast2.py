import ast
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
import difflib


class ChangeType(BaseModel):
    type: str  # 'no_change', 'minor', 'significant', 'major'
    description: str
    priority: int


class FunctionChange(BaseModel):
    name: str
    signature_change: Optional[ChangeType] = None
    body_changes: List[ChangeType] = Field(default_factory=list)
    nested_function_change: Optional[ChangeType] = None


class ClassMethodChange(BaseModel):
    class_name: str
    method_name: str
    signature_change: Optional[ChangeType] = None
    body_changes: List[ChangeType] = Field(default_factory=list)


class ChangeAnalysis(BaseModel):
    added_functions: List[str] = Field(default_factory=list)
    removed_functions: List[str] = Field(default_factory=list)
    changed_functions: List[FunctionChange] = Field(default_factory=list)
    changed_class_methods: List[ClassMethodChange] = Field(
        default_factory=list)


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


class CodeChangeAnalyzer:
    def __init__(self, old_code: str, new_code: str):
        self.old_code = old_code
        self.new_code = new_code
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
            if self._has_significant_changes(function_change):
                changes.changed_functions.append(function_change)

        changes.changed_class_methods = self._analyze_class_method_changes()

        return changes

    def _has_significant_changes(self, change: FunctionChange) -> bool:
        return (change.signature_change is not None or
                len(change.body_changes) > 0 or
                change.nested_function_change is not None)
 
        return FunctionChange(
            name=func_name,
            signature_change=signature_change,
            body_changes=body_changes,
            nested_function_change=nested_function_change
        )

    def _analyze_signature_change(self, old_func: ast.FunctionDef, new_func: ast.FunctionDef) -> Optional[ChangeType]:
        old_args = ast.dump(old_func.args)
        new_args = ast.dump(new_func.args)
        if old_args != new_args:
            return ChangeType(type="significant", description="Function signature changed", priority=8)
        return None

    def _analyze_body_changes(self, old_func: ast.FunctionDef, new_func: ast.FunctionDef) -> List[ChangeType]:
        old_body = ast.unparse(old_func).split('\n')
        new_body = ast.unparse(new_func).split('\n')

        changes = []
        diff = list(difflib.unified_diff(old_body, new_body, n=0))

        for line in diff[2:]:  # Skip the first two lines of unified diff output
            if line.startswith('+') or line.startswith('-'):
                change_type = self._categorize_change(line[1:])
                changes.append(change_type)

        return changes

    def _categorize_change(self, line: str) -> ChangeType:
        stripped_line = line.strip()

        # Check for comment changes
        if stripped_line.startswith('#'):
            return ChangeType(type="minor", description="Comment changed", priority=1)

        # Check for import changes
        if stripped_line.startswith('import ') or stripped_line.startswith('from '):
            return ChangeType(type="significant", description="Import statement changed", priority=7)

        # Check for whitespace-only changes
        if not stripped_line:
            return ChangeType(type="minor", description="Whitespace change", priority=1)

        # Check for simple variable assignment
        if '=' in stripped_line and not any(keyword in stripped_line for keyword in ['if', 'for', 'while', 'def', 'class']):
            return ChangeType(type="minor", description="Variable assignment changed", priority=3)

        # Check for control flow changes
        if any(keyword in stripped_line for keyword in ['if', 'else', 'elif', 'for', 'while', 'try', 'except', 'with']):
            return ChangeType(type="major", description="Control flow changed", priority=9)

        # Check for function or class definition
        if stripped_line.startswith('def ') or stripped_line.startswith('class '):
            return ChangeType(type="major", description="Function or class definition changed", priority=10)

        # Default to significant change
        return ChangeType(type="significant", description="Code logic changed", priority=5)

    def _analyze_nested_function_change(self, old_func: ast.FunctionDef, new_func: ast.FunctionDef) -> Optional[ChangeType]:
        old_nested = set(node.name for node in ast.walk(
            old_func) if isinstance(node, ast.FunctionDef) and node != old_func)
        new_nested = set(node.name for node in ast.walk(
            new_func) if isinstance(node, ast.FunctionDef) and node != new_func)

        if old_nested != new_nested:
            return ChangeType(type="major", description="Nested function structure changed", priority=9)
        return None

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

                signature_change = self._analyze_signature_change(
                    old_method, new_method)
                body_changes = self._analyze_body_changes(
                    old_method, new_method)

                if signature_change or body_changes:
                    changed_methods.append(ClassMethodChange(
                        class_name=class_name,
                        method_name=method_name,
                        signature_change=signature_change,
                        body_changes=body_changes
                    ))

        return changed_methods


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

def unchanged_function():
    pass
"""

new_code = """
def greet(name, greeting="Hello"):
    # A friendly greeting function
    print(f"{greeting}, {name}!")

class Calculator:
    def add(self, a, b):
        result = a + b
        return result

def process_data(data):
    while data:
        item = data.pop()
        print(item)

def unchanged_function():
    pass

def new_function():
    pass
"""

analyzer = CodeChangeAnalyzer(old_code, new_code)
changes = analyzer.analyze_changes()

print(changes.model_dump_json(indent=2))
