# Reference
HERMES is a namespace framework, which allows easy installation of support for additional Nodes
as pip packages that become available under the same namespace `hermes.<new_package>`.
Specifying

!!! tip "Adding a new `Node`"
    
    Integrating user-defined new Node into the rest of the framework is trivial.
    Wrap the custom logic, including non-HERMES code, in the [provided template](https://github.com/maximyudayev/hermes-template).

HERMES follows the [PEP 8](https://peps.python.org/pep-0008/) public/private method naming convention.

!!! note "Regular users"

    Only use the available public methods, without leading underscores `_<method_name>()`.
    The private methods are shown for informative purposes only.
    Extending the system to new sensors is easy with ready-made templates and provided
    decoupling from the low-level controls.

!!! tip "Developers"

    When extending the system functionality, understanding of low-level methods could
    become useful. Private methods also influence performance and could be the first place
    to look for enhancements.
