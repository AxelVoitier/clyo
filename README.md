# Clyo

[![PyPI - Version](https://img.shields.io/pypi/v/clyo?style=for-the-badge)](https://pypi.python.org/pypi/clyo)
[![PyPI - Status](https://img.shields.io/pypi/status/clyo?style=for-the-badge)](https://pypi.python.org/pypi/clyo)
[![PyPI - Download](https://img.shields.io/pypi/dm/clyo?style=for-the-badge)](https://pypi.python.org/pypi/clyo)
[![PyPI - Python version](https://img.shields.io/pypi/pyversions/clyo?style=for-the-badge)](https://pypi.python.org/pypi/clyo)
[![GitHub - License](https://img.shields.io/github/license/AxelVoitier/clyo?style=for-the-badge)](https://github.com/AxelVoitier/clyo/blob/master/LICENSE)

[![Lines of code](https://img.shields.io/tokei/lines/github/AxelVoitier/clyo?style=for-the-badge)](https://github.com/AxelVoitier/clyo)
[![GitHub - Commits since](https://img.shields.io/github/commits-since/AxelVoitier/clyo/1.0.0?style=for-the-badge)](https://github.com/AxelVoitier/clyo/commits/master)
[![GitHub - Workflow](https://img.shields.io/github/workflow/status/AxelVoitier/clyo/Python%20package?style=for-the-badge)](https://github.com/AxelVoitier/clyo/actions)
<!---
[![Codecov](https://img.shields.io/codecov/c/gh/AxelVoitier/clyo?style=for-the-badge)](https://codecov.io/gh/AxelVoitier/clyo)
--->

Give your Python scripts various flavours of CLI!

Based on [click](https://palletsprojects.com/p/click/) and [typer](https://github.com/tiangolo/typer), it improves on them with:

- An integrated prompt/REPL, using [prompt-toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit)
  - Makes invoking your commands more interactive
  - Shows inline completion suggestions and help
  - Dedicated history for your tool
- Better hierarchical presentation of `--help` when using sub-commands
- A default callback for `typer` that handles:
  - Logging levels (verbose, and quiet flags as increments)
  - A prettier console logging handler (using [rich](https://github.com/Textualize/rich))
  - Loading a user config file (agnostic of the format), specified either by an option, or an environment variable
  - Configurable pretty tracebacks (from `rich`)

-----

**Table of Contents**

- [Installation](#installation)
- [Usage](#usage)
- [License](#license)

## Installation

```console
pip install clyo
```

## Usage

### Quick trial

Clyo can be used as a drop-in replacement to [typer](https://github.com/tiangolo/typer):
```python
from clyo import Clyo as Typer, Argument, Option

cli = Typer(...)
```

Which makes it very easy to trial. Note however that once you are committed to use Clyo,
it would be preferable to use its real names, as in the future we might bypass `typer` entirely.

### Using the main command callback

```python
import logging
import sys
from configparser import ConfigParser
from pathlib import Path

import clyo

OURSELF = Path(__file__).resolve()
BASE_PATH = OURSELF.parent
NAME = Path(sys.argv[0]).stem  # Or use OURSELF.stem

logger = logging.getLogger(NAME)
config = ConfigParser()
cli = clyo.Clyo(help='Example of Clyo features')


if __name__ == '__main__':
    cli.set_main_callback(
        NAME,
        config=config,
        default_config_path=Path('config.cfg'),
    )

    cli(prog_name=NAME)
```

### Using the prompt/REPL

Starting from previous example:
```python
from clyo import CommandTree

...

@cli.command(hidden=True)
def prompt() -> None:
    command_tree = CommandTree(cli)
    session = command_tree.make_prompt_session()

    try:
        while True:
            command_tree.repl(session)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    cli.set_main_callback(
        NAME,
        config=config,
        default_config_path=Path('config.cfg'),
        default_command=prompt,
    )

    cli(prog_name=NAME)
```

Now if you invoke your tool without any command, it will start the prompt.

You can also customise the prompt either by manipulating the session object, or by passing
some of the [prompt-toolkit `prompt()` arguments](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/reference.html#prompt_toolkit.shortcuts.prompt) to the `repl()` method.

To customise the REPL loop further you might as well look at the source of `repl()`
and reimplement one yourself, using the other features of `CommandTree` (eg. `completer` property,
`get_command()`/`__getitem__()`, `goto()`, etc.). `CommandTree` is going go be your glue between
the Clyo/Typer/Click set of commands, and your prompt-toolkit application.

## License

`clyo` is distributed under the terms of the [MPLv2](https://spdx.org/licenses/MPL-2.0.html) license.
