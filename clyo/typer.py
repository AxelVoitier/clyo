# Copyright (c) 2022 Contributors as noted in the AUTHORS file
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# System imports
import logging
import sys
from pathlib import Path
from typing import Optional

# Third-party imports
import click
import typer
from rich import box
from rich.console import Capture
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from typer import Option
from typer.core import TyperGroup

# Local imports

# While Typer and Rich are great out-of-the-box, as soon as you need a customisation not already
# planned for, it gets very quickly attrocious to make them do what you want...

# Monkey patching rich utils to customise help printout without reimplementing it all
_options_panels = None
_commands_pannels = None


def _print_options_panel(*args, **kwargs):
    if _options_panels is not None:  # Save the call for later
        _options_panels.append((args, kwargs))
    else:
        return typer.rich_utils._orig_print_options_panel(*args, **kwargs)


def _print_commands_panel(*args, **kwargs):
    if _commands_pannels is not None:  # Save the call for later
        _commands_pannels.append((args, kwargs))
    else:
        return typer.rich_utils._orig_print_commands_panel(*args, **kwargs)


typer.rich_utils._orig_print_options_panel = typer.rich_utils._print_options_panel
typer.rich_utils._print_options_panel = _print_options_panel
typer.rich_utils._orig_print_commands_panel = typer.rich_utils._print_commands_panel
typer.rich_utils._print_commands_panel = _print_commands_panel


def _print_commands_panel_with_tree(*, name, commands, markup_mode, console, ctx):
    '''Reimplements to (recursively) show subcommands of given commands, in a tree form'''

    t_styles = {
        "show_lines": typer.rich_utils.STYLE_COMMANDS_TABLE_SHOW_LINES,
        "leading": typer.rich_utils.STYLE_COMMANDS_TABLE_LEADING,
        "box": typer.rich_utils.STYLE_COMMANDS_TABLE_BOX,
        "border_style": typer.rich_utils.STYLE_COMMANDS_TABLE_BORDER_STYLE,
        "row_styles": typer.rich_utils.STYLE_COMMANDS_TABLE_ROW_STYLES,
        "pad_edge": typer.rich_utils.STYLE_COMMANDS_TABLE_PAD_EDGE,
        "padding": typer.rich_utils.STYLE_COMMANDS_TABLE_PADDING,
    }
    box_style = getattr(box, t_styles.pop("box"), None)

    commands_tree = Tree('root', hide_root=True, style='bold cyan')
    commands_table = Table(
        highlight=False,
        show_header=False,
        expand=True,
        box=box_style,
        **t_styles,
    )
    # Define formatting in first column, as commands don't match highlighter
    # regex
    commands_table.add_column(no_wrap=True)
    help_rows = []
    deprecated_rows = []

    def make_row_info(command):
        command_name = command.name or ""

        help_text = command.short_help or command.help or ""
        help_text = typer.rich_utils._make_command_help(
            help_text=help_text,
            markup_mode=markup_mode,
        )

        if command.deprecated:
            command_name_text = Text(
                f"{command_name}", style=typer.rich_utils.STYLE_DEPRECATED_COMMAND)
            deprecated_text = Text(typer.rich_utils.DEPRECATED_STRING,
                                   style=typer.rich_utils.STYLE_DEPRECATED)
        else:
            command_name_text = Text(command_name)
            deprecated_text = None

        return command_name_text, help_text, deprecated_text

    def walk_commands(commands, root):
        for command in commands:
            command_name_text, help_text, deprecated_text = make_row_info(command)

            leaf = root.add(command_name_text)
            help_rows.append(help_text)
            deprecated_rows.append(deprecated_text)

            if not isinstance(command, click.MultiCommand):
                continue

            if isinstance(command, click.Group):
                # Conserve declaration order
                subcommands = command.commands.values()
            else:
                subcommands = [command.get_command(name) for name in command.list_commands(ctx)]

            walk_commands(subcommands, leaf)

    walk_commands(commands, commands_tree)

    # A Tree cannot have columns on its side.
    # We also cannot just add a Tree to a Table as we cannot extract each entry of a Tree
    # as RenderableType. Instead, we make it print on the console, but capture its output.
    # Then, we extract each line, and turn them into Text (taking into account they might
    # have some style already, which should not count in their length).
    with Capture(console) as capture:
        console.print(commands_tree)
    commands_rows = [Text.from_ansi(command) for command in capture.get().splitlines()]

    if any(deprecated_rows):
        it = zip(commands_rows, help_rows, deprecated_rows)
    else:
        it = zip(commands_rows, help_rows)
    [commands_table.add_row(*fields) for fields in it]

    if commands_table.row_count:
        console.print(
            Panel(
                commands_table,
                border_style=typer.rich_utils.STYLE_COMMANDS_PANEL_BORDER,
                title=name,
                title_align=typer.rich_utils.ALIGN_COMMANDS_PANEL,
            )
        )


class CommandsFormatterMixin:  # Can be used on any click.Command subclass

    def format_help(self, ctx, formatter) -> None:
        global _options_panels, _commands_pannels
        _options_panels = []
        _commands_pannels = []

        try:
            to_return = typer.rich_utils.rich_format_help(
                obj=self,
                ctx=ctx,
                markup_mode=self.rich_markup_mode,
            )

            # First, we print commands before arguments and options, because the parameters
            # of a group callback are usually seldom used, whereas the commands are what people
            # are looking for most of the time
            for args, kwargs in _commands_pannels:
                # Second, we use our custom command tree printer, because you rather want to
                # have a quick overview of all subcommands directly, instead of getting the help
                # of each command to see what each do
                _print_commands_panel_with_tree(*args, ctx=ctx, **kwargs)

            for args, kwargs in _options_panels:
                typer.rich_utils._orig_print_options_panel(*args, **kwargs)

            return to_return

        finally:
            _options_panels = None
            _commands_pannels = None


class ClyoTyperGroup(CommandsFormatterMixin, TyperGroup):

    def get_help_option(self, ctx):
        '''Part one of assigning a rich panel to default options related to the CLI itself'''

        opt = super().get_help_option(ctx)
        if opt:
            opt.rich_help_panel = 'CLI'
        return opt


class ClyoTyper(typer.Typer):

    def __init__(
        self, *args,
        help='CLI for ...',
        rich_markup_mode='markdown',
        cls=ClyoTyperGroup, **kwargs
    ):
        parent = kwargs.pop('parent', None)
        super().__init__(
            *args,
            help=help,
            rich_markup_mode=rich_markup_mode,
            cls=cls,
            **kwargs
        )

        if parent:
            parent.add_typer(self)

    def add_typer(self, *args, **kwargs):
        '''Reimplements to inject cls argument on sub-groups'''
        if 'cls' not in kwargs:
            kwargs['cls'] = ClyoTyperGroup

        return super().add_typer(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        '''
        Reimplements for part two of assigning a rich panel to default options
        related to the CLI itself
        '''
        if sys.excepthook != typer.main.except_hook:
            sys.excepthook = typer.main.except_hook

        cmd = typer.main.get_command(self)
        for param in cmd.params:
            if param.name in ('install_completion', 'show_completion'):
                param.rich_help_panel = 'CLI'

        try:
            cmd(*args, **kwargs)
        except Exception as e:
            setattr(
                e,
                typer.main._typer_developer_exception_attr_name,
                typer.models.DeveloperExceptionConfig(
                    pretty_exceptions_enable=self.pretty_exceptions_enable,
                    pretty_exceptions_show_locals=self.pretty_exceptions_show_locals,
                    pretty_exceptions_short=self.pretty_exceptions_short,
                ),
            )

            # We want to log the exception, in particular if we have file handlers.
            # But typer is also configured to print nice stack trace in console.
            # If our loggers are configured also with a console logger,
            # then we want to avoids dual printing of stack trace in console.
            root_logger = logging.getLogger('')
            file_handler = None
            for handler in root_logger.handlers:
                if not isinstance(handler, logging.FileHandler):
                    continue
                file_handler = handler
                break

            if file_handler:
                print_err_logger = logging.getLogger('print_err')
                print_err_logger.addHandler(file_handler)
                # Prevents it to fowrward the record to parent handlers:s
                print_err_logger.propagate = False
                print_err_logger.exception('Oups')

            raise e

    def set_main_callback(
        self, NAME, *,
        config=None, default_config_path=None,
        default_command=None
    ):
        if default_config_path is None:
            default_config_path = Path(typer.get_app_dir(NAME)) / 'config.cfg'

        @self.callback(invoke_without_command=(default_command is not None))
        def cli_base(
            ctx: typer.Context,
            config_file: Optional[Path] = Option(
                default_config_path, '--config', '-c', help='Config file',
                file_okay=True, envvar=f'{NAME.upper().replace(" ", "_").replace("-", "_")}_CONFIG',
                rich_help_panel='CLI'
            ),
            verbose: int = Option(0, '--verbose', '-v', count=True, show_default=False,
                                  help='Increase logging output', rich_help_panel='Logging'),
            quiet: int = Option(0, '--quiet', '-q', count=True, show_default=False,
                                help='Decrease logging output', rich_help_panel='Logging'),
            log_lvl: str = Option('INFO', help='Log level', rich_help_panel='Logging'),
        ):
            # Config file
            if config is not None:
                config.read(config_file)

            # Configure logging
            root_logger = logging.getLogger()
            # Compute target log level from given log_level + number of quiet - number of verbose
            levels = sorted(set(logging._nameToLevel.values()))
            root_logger.setLevel(levels[min(max(levels.index(
                logging.getLevelName(log_lvl)) + quiet - verbose, 0), len(levels) - 1)])

            # Make console logging attractive
            console_handler = RichHandler(
                rich_tracebacks=True,
                tracebacks_suppress=[typer, click],
                tracebacks_show_locals=True
            )
            root_logger.addHandler(console_handler)

            if (ctx.invoked_subcommand is None) and (default_command is not None):
                default_command()
