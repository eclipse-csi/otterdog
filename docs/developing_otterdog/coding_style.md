# Coding & Style Guidelines

This document describes the coding and documentation style guidelines for contributing to Otterdog. Please follow these guidelines to ensure consistency across the codebase.


## Code style and requirements

TODO

## Documentation style

Documentation is written in Markdown and built using [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/).

### Code documentation

When contributing to otterdog, please make sure that all code is well documented. The following should be documented using properly formatted docstrings:

- Modules
- Class definitions
- Function definitions
- Module-level variables

Otterdog uses [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) formatted according to [PEP 257](https://www.python.org/dev/peps/pep-0257/) guidelines. (See [Example Google Style Python Docstrings](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_google.html) for further examples.)

Where this is a conflict between Google-style docstrings and pydocstyle linting, follow the pydocstyle linting hints.

Class attributes and function arguments should be documented in the format "name: description." When applicable, a return type should be documented with just a description. Types are inferred from the signature.

```python
class Foo:
    """A class docstring.

    Attributes:
        bar: A description of bar. Defaults to "bar".
    """

    bar: str = 'bar'
```

```python
def bar(self, baz: int) -> str:
    """A function docstring.

    Args:
        baz: A description of `baz`.

    Returns:
        A description of the return value.
    """

    return 'bar'
```

You may include example code in docstrings. This code should be complete, self-contained, and runnable. Docstring examples are tested using [doctest](https://docs.python.org/3/library/doctest.html), so make sure they are correct and complete.

!!! note "Class and instance attributes"
    Class attributes should be documented in the class docstring.

    Instance attributes should be documented as "Args" in the `__init__` docstring.
