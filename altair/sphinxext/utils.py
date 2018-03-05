import sys
import ast
from contextlib import contextmanager


class _CatchDisplay(object):
    """Class to temporarily catch sys.displayhook"""
    def __init__(self):
        self.output = None

    def __enter__(self):
        self.old_hook = sys.displayhook
        sys.displayhook = self
        return self

    def __exit__(self, type, value, traceback):
        sys.displayhook = self.old_hook
        # Returning False will cause exceptions to propagate
        return False

    def __call__(self, output):
        self.output = output


def exec_then_eval(code, namespace=None, filename='<string>'):
    """
    Execute a multi-line block of code in the given namespace

    If the final statement in the code is an expression, return
    the result of the expression.
    """
    tree = ast.parse(code, filename='<ast>', mode='exec')
    if namespace is None:
        namespace = {}
    catch_display = _CatchDisplay()

    if isinstance(tree.body[-1], ast.Expr):
        to_exec, to_eval = tree.body[:-1], tree.body[-1:]
    else:
        to_exec, to_eval = tree.body, []

    for node in to_exec:
        compiled = compile(ast.Module([node]),
                           filename=filename, mode='exec')
        exec(compiled, namespace)

    with catch_display:
        for node in to_eval:
            compiled = compile(ast.Interactive([node]),
                               filename=filename, mode='single')
            exec(compiled, namespace)

    return catch_display.output


SYNTAX_ERROR_DOCSTRING = """
SyntaxError
===========
Example script with invalid Python syntax
"""

def _parse_source_file(filename):
    """Parse source file into AST node

    Parameters
    ----------
    filename : str
        File path

    Returns
    -------
    node : AST node
    content : utf-8 encoded string

    Notes
    -----
    This function adapted from the sphinx-gallery project; license: BSD-3
    https://github.com/sphinx-gallery/sphinx-gallery/
    """

    # can't use codecs.open(filename, 'r', 'utf-8') here b/c ast doesn't
    # work with unicode strings in Python2.7 "SyntaxError: encoding
    # declaration in Unicode string" In python 2.7 the string can't be
    # encoded and have information about its encoding. That is particularly
    # problematic since source files include in their header information
    # about the file encoding.
    # Minimal example to fail: ast.parse(u'# -*- coding: utf-8 -*-')

    with open(filename, 'rb') as fid:
        content = fid.read()
    # change from Windows format to UNIX for uniformity
    content = content.replace(b'\r\n', b'\n')

    try:
        node = ast.parse(content)
        return node, content.decode('utf-8')
    except SyntaxError:
        return None, content.decode('utf-8')


def get_docstring_and_rest(filename):
    """Separate ``filename`` content between docstring and the rest

    Strongly inspired from ast.get_docstring.

    Parameters
    ----------
    filename: str
        The path to the file containing the code to be read

    Returns
    -------
    docstring: str
        docstring of ``filename``
    rest: str
        ``filename`` content without the docstring
    lineno: int
         the line number on which the code starts

    Notes
    -----
    This function adapted from the sphinx-gallery project; license: BSD-3
    https://github.com/sphinx-gallery/sphinx-gallery/
    """
    node, content = _parse_source_file(filename)

    if node is None:
        return SYNTAX_ERROR_DOCSTRING, content, 1

    if not isinstance(node, ast.Module):
        raise TypeError("This function only supports modules. "
                        "You provided {0}".format(node.__class__.__name__))
    try:
        # in python 3.7 module knows it's docstring
        # everything else will raise an attribute error
        docstring = node.docstring

        import tokenize
        from io import BytesIO
        ts = tokenize.tokenize(BytesIO(content).readline)
        ds_lines = 0
        # find the first string according to the tokenizer and get
        # it's end row
        for tk in ts:
            if tk.exact_type == 3:
                ds_lines, _ = tk.end
                break
        # grab the rest of the file
        rest = '\n'.join(content.split('\n')[ds_lines:])
        lineno = ds_lines + 1

    except AttributeError:
        # this block can be removed when python 3.6 support is dropped
        if node.body and isinstance(node.body[0], ast.Expr) and \
           isinstance(node.body[0].value, ast.Str):
            docstring_node = node.body[0]
            docstring = docstring_node.value.s
            # python2.7: Code was read in bytes needs decoding to utf-8
            # unless future unicode_literals is imported in source which
            # make ast output unicode strings
            if hasattr(docstring, 'decode') and not isinstance(docstring, unicode):
                docstring = docstring.decode('utf-8')
            lineno = docstring_node.lineno  # The last line of the string.
            # This get the content of the file after the docstring last line
            # Note: 'maxsplit' argument is not a keyword argument in python2
            rest = content.split('\n', lineno)[-1]
            lineno += 1
        else:
            docstring, rest = '', ''

    if not docstring:
        raise ValueError(('Could not find docstring in file "{0}". '
                          'A docstring is required for the example gallery.')
                         .format(filename))
    return docstring, rest, lineno
