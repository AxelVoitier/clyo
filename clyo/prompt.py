# Copyright (c) 2022 Contributors as noted in the AUTHORS file
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# pyright: reportPrivateUsage=false
from __future__ import annotations

# System imports
import sys
from dataclasses import dataclass, field
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Iterable, Mapping, Callable
    from typing import Any, Self, TypeAlias

    from click import Command
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.formatted_text import AnyFormattedText
    from rich.console import RenderableType

# Third-party imports
import click
import typer
import typer.core
from click.parser import split_opt
from prompt_toolkit import ANSI
from prompt_toolkit.completion import (
    NestedCompleter, Completer, FuzzyCompleter, WordCompleter,
    Completion,
)
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import FormattedText
from rich import print as rprint
from rich.text import Text
from typer.main import get_command
from typer import rich_utils

# Local imports


DEBUG = True


def print_in_terminal(*args: Any, **kwargs: Any) -> None:
    if not DEBUG:
        return

    from prompt_toolkit.application import run_in_terminal

    def _() -> None:
        print(*args, **kwargs)

    run_in_terminal(_)


def rich_to_ptk(*renderables: RenderableType) -> ANSI:
    console = rich_utils._get_rich_console()
    console.begin_capture()

    for renderable in renderables:
        console.print(renderable, end='')

    rendered = console.end_capture()
    return ANSI(rendered.strip())


class RootCompleter(Completer):

    def __init__(self, level: Completer, root: Node) -> None:
        self._level = level
        self._root = root

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent
    ) -> Iterator[Completion]:
        # print_in_terminal(f'\n---------\nNew completion: |{document.text}|')
        if document.text.startswith('help '):
            document = Document(
                document.text.replace('help ', ''),
                cursor_position=document.cursor_position - 5,
            )

        if document.text.startswith('/'):
            new_doc = Document(
                document.text[1:].replace('/', ' '),
                cursor_position=document.cursor_position - 1,
            )
            yield from self._root.completer.get_completions(new_doc, complete_event)
        else:
            new_doc = Document(
                document.text.replace('/', ' '),
                cursor_position=document.cursor_position,
            )
            yield from self._level.get_completions(new_doc, complete_event)


class NestedCompleterWithExtra(NestedCompleter):

    if TYPE_CHECKING:
        Option: TypeAlias = tuple[
            Completer | None,  # Option
            AnyFormattedText,  # Display
            AnyFormattedText,  # Meta
            dict[str, Any]  # Option kwargs
        ]
        Argument: TypeAlias = tuple[
            AnyFormattedText,  # Display
            AnyFormattedText,  # Meta
            dict[str, Any]  # Option kwargs
        ]

    def __init__(
        self,
        options_with_extra: Mapping[str, NestedCompleterWithExtra.Option],
        *args: Any,
        arguments: Iterable[Argument] | None = None,
        **kwargs: Any,
    ) -> None:
        self._display_dict: dict[str, AnyFormattedText] = {}
        self._meta_dict: dict[str, AnyFormattedText] = {}
        self._hidden: dict[str, Completer | None] = {}
        options: dict[str, Completer | None] = {}

        for name, (option, display, meta, opt_kwargs) in options_with_extra.items():
            if opt_kwargs.get('hidden', False):
                self._hidden[name] = option
            else:
                options[name] = option
                self._display_dict[name] = display
                self._meta_dict[name] = meta

        self._arguments: list[Completion] = []
        if arguments:
            for display, meta, arg_kwargs in arguments:
                if arg_kwargs.get('hidden', False):
                    continue

                self._arguments.append(Completion(
                    text='',
                    start_position=0,
                    display=display,
                    display_meta=meta,
                ))

        super().__init__(options, *args, **kwargs)

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent
    ) -> Iterator[Completion]:
        text = document.text_before_cursor.lstrip()
        stripped_len = len(document.text_before_cursor) - len(text)

        # print_in_terminal(f'\n|{document.text=}| ; |{text=}|')

        if ' ' in text:
            terms = text.split()
            completer = self.options.get(terms[0]) or self._hidden.get(terms[0])

            # If we have a sub completer, use this for the completions.
            if completer is not None:
                remaining_text = text[len(terms[0]):].lstrip()
                move_cursor = len(text) - len(remaining_text) + stripped_len

                new_document = Document(
                    remaining_text,
                    cursor_position=document.cursor_position - move_cursor,
                )

                # print_in_terminal(f'We have a completer, forwarding |{new_document.text}|')
                yield from completer.get_completions(new_document, complete_event)
                return

        if text.endswith(' '):
            # print_in_terminal('Space at the end, trimming')
            new_document = Document(
                '',
                cursor_position=0,
            )

        elif ' ' in text:  # No subcompleter this time (eg. some parameter are given)
            # print_in_terminal(f'{terms=}')
            remaining_text = terms[-1]  # type: ignore[reportUnboundVariable]
            move_cursor = len(text) - len(remaining_text) + stripped_len

            new_document = Document(
                remaining_text,
                cursor_position=document.cursor_position - move_cursor,
            )

        else:
            new_document = document
        # print_in_terminal(f'document: |{new_document.text}|')

        # print_in_terminal('options:', list(self.options.keys()))
        # print_in_terminal('args', self._arguments)

        completer = WordCompleter(
            list(self.options.keys()),
            ignore_case=self.ignore_case,
            display_dict=self._display_dict,
            meta_dict=self._meta_dict,
        )
        for completion in completer.get_completions(new_document, complete_event):
            if completion.text in text:
                continue
            # print_in_terminal('yielding opt', completion)
            yield completion

        if not new_document.text:
            nargs = len([term for term in text.split() if '=' not in term])
            for arg in self._arguments[nargs:]:
                # print_in_terminal('yielding arg', arg)
                yield arg


@dataclass
class Node:
    name: str
    command: click.Command
    parent: Self | None = None
    path: Path = field(init=False)
    children: dict[str, Self] = field(default_factory=dict, init=False)
    completer: Completer = field(init=False)

    def __post_init__(self) -> None:
        if self.parent:
            self.path = self.parent.path / self.name
        else:
            self.path = CommandTree.ROOT_PATH / self.name

        if isinstance(self.command, click.Group):
            self.children = dict(self.make_recursive(self.command, self))
            self._make_group_completer()
        else:
            self._make_command_completer()

    @classmethod
    def make_recursive(
        cls,
        command: Command,
        parent: Node | None = None
    ) -> Iterator[tuple[str, Self]]:
        if isinstance(command, click.Group):
            for subcommand in command.commands.values():
                node = cls(
                    name=subcommand.name or '',
                    command=subcommand,
                    parent=parent,
                )

                yield node.name, node
        else:
            raise NotImplementedError('Don\'t know what to do with a command that is not a group?!')

    def exec(self, args: str | None = None) -> None:
        try:
            self.command(
                self.make_args(args) if args else [],
                prog_name=str(self.path),
                # standalone_mode=False,
            )
        except SystemExit:
            pass
        except click.ClickException as ex:
            ex.show()
        except click.Abort:
            rprint('[red]Aborted![/]', file=sys.stderr)
        except Exception as ex:
            rprint('[red]Exception:[/]', ex, file=sys.stderr)

    @property
    def _options_trans(self) -> dict[str, str]:
        parser = self.command.make_parser(click.get_current_context())
        return {
            split_opt(opt)[1]: opt
            for opt in chain(
                parser._short_opt.keys(),
                parser._long_opt.keys(),
            )
        }

    def make_args(self, args_string: str) -> list[str] | None:
        args: list[str] | None = None
        if args_string:
            args = []
            opts = self._options_trans
            for arg in args_string.split(' '):
                if not arg:
                    continue
                if '=' in arg:
                    opt, value = arg.split('=', maxsplit=1)
                    if opt in opts:
                        if value:
                            args.append(f'{opts[opt]}={value}')
                        else:
                            args.append(opts[opt])
                    else:
                        args.append(arg)
                else:
                    args.append(arg)

        return args or None

    def _make_group_completer(self) -> None:
        completion_dict: dict[str, NestedCompleterWithExtra.Option] = {}
        for node in self.children.values():
            completion_dict[node.name] = (
                node.completer,
                None,
                rich_to_ptk(rich_utils._make_rich_rext(
                    text=(node.command.help or ' ').splitlines()[0].strip(),
                    markup_mode=getattr(node.command, 'rich_markup_mode', None),
                )),
                dict(hidden=node.command.hidden),
            )

        self.completer = NestedCompleterWithExtra(dict(completion_dict))

    def _make_command_completer(self) -> None:
        completion_dict: dict[str, NestedCompleterWithExtra.Option] = {}
        argument_list: list[NestedCompleterWithExtra.Argument] = []
        markup_mode: rich_utils.MarkupMode = getattr(self.command, 'rich_markup_mode', None)

        for param in self.command.params:
            # Metavar
            metavar_text = Text(style='bold blue')
            metavar_str = param.make_metavar()
            if (
                isinstance(param, click.Argument)
                and param.name
                and metavar_str == param.name.upper()
            ):
                metavar_str = param.type.name.upper()
            if metavar_str == 'BOOLEAN':
                metavar_str = 'FLAG'
            if metavar_str:
                metavar_text.append(metavar_str)
                metavar_text.append(' ')

            # Range
            try:
                # skip count with default range type
                if (
                    isinstance(param.type, click.types._NumberRangeBase)
                    and isinstance(param, click.Option)
                    and not (param.count and param.type.min == 0 and param.type.max is None)
                ):
                    range_str = param.type._describe_range()
                    if range_str:
                        metavar_text.append(f'[{range_str}] ')
            except AttributeError:
                # click.types._NumberRangeBase is only in Click 8x onwards
                pass

            # Default
            default_text = Text(style='magenta dim')
            default_str = ''
            if isinstance(param, (typer.core.TyperOption, typer.core.TyperArgument)):
                if param.show_default:
                    ctx = click.get_current_context()
                    show_default_is_str = isinstance(param.show_default, str)
                    default_value = param._extract_default_help_str(ctx=ctx)
                    default_str = param._get_default_string(
                        ctx=ctx,
                        show_default_is_str=show_default_is_str,
                        default_value=default_value,
                    )
            if default_str:
                default_text.append(f'({default_str}) ')

            # Help text
            if isinstance(param, (click.Option, typer.core.TyperArgument)):
                help = param.help or ' '
            else:
                help = ' '
            help_str = help.splitlines()[0].strip()
            help_text = rich_utils._make_rich_rext(text=help_str, markup_mode=markup_mode)

            meta_str = rich_to_ptk(metavar_text, default_text, help_text)

            if isinstance(param, click.Option):
                if param.is_bool_flag and param.default:
                    # The flag is on by default. Use secondary opts
                    opts = param.secondary_opts
                else:
                    opts = param.opts

                for opt in opts:
                    if param.is_flag:
                        opt_name = opt
                    else:
                        opt_name = f'{split_opt(opt)[1]}='

                    display = None
                    if param.required:
                        display = FormattedText([('bold', opt_name)])

                    completion_dict[opt_name] = (
                        None,
                        display,
                        meta_str,
                        dict(hidden=param.hidden),
                    )

                    break  # Only one per param

            elif isinstance(param, click.Argument):
                display = f'<{param.human_readable_name}>'
                if param.required:
                    display = FormattedText([('bold', display)])
                if isinstance(param, (click.Option, typer.core.TyperArgument)):
                    hidden = param.hidden
                else:
                    hidden = False

                argument_list.append((
                    display,
                    meta_str,
                    dict(hidden=hidden),
                ))

        self.completer = NestedCompleterWithExtra(completion_dict, arguments=argument_list)


class CommandTree:

    ROOT_PATH = Path('/')

    def __init__(self, cli: typer.Typer | click.Command) -> None:
        self._cli = cli
        root_command = self._cli
        if isinstance(root_command, typer.Typer):
            root_command = get_command(root_command)
        self._root = Node(
            name='',
            command=root_command,
        )
        self._pointer = self._root

        self._prefixes: dict[str, Callable[[str], tuple[Node, str]]] = {}
        self.add_prefix('help', self._help_prefix)
        self.add_prefix('?', self._help_prefix)

    @property
    def path(self) -> Path:
        return self._pointer.path

    @property
    def completer(self) -> Completer:
        return FuzzyCompleter(RootCompleter(self._pointer.completer, self._root))
        # return RootCompleter(self._pointer.completer, self._root)

    @property
    def at_root(self) -> bool:
        return (self.path == self.ROOT_PATH)

    def add_prefix(self, name: str, callback: Callable[[str], tuple[Node, str]]) -> None:
        self._prefixes[name] = callback

    def _help_prefix(self, args: str) -> tuple[Node, str]:
        if args.strip():
            command, _ = self.get_command(args, prefix_enabled=False)
        else:
            command = self._pointer

        return command, '--help'

    def __getitem__(self, name: str) -> tuple[Node, str]:
        return self.get_command(name, prefix_enabled=True)

    def get_command(self, prompt: str, prefix_enabled: bool = True) -> tuple[Node, str]:
        if '#' in prompt:
            prompt = prompt[:prompt.index('#')]

        fields = prompt.strip().split(' ', maxsplit=1)
        command = fields.pop(0)
        args = fields.pop() if fields else ''

        pointer = self._pointer
        if command.startswith('/'):
            pointer = self._root

        while command:
            fields = command.lstrip('/').split('/', maxsplit=1)
            subpath = fields.pop(0)
            command = fields.pop() if fields else ''

            if subpath == '..':
                pointer = pointer.parent if pointer.parent else pointer
            elif subpath:  # If not, do nothing. Handles case of just '/'
                try:
                    pointer = pointer.children[subpath]
                except KeyError:
                    if prefix_enabled and (not command) and (subpath in self._prefixes):
                        return self._prefixes[subpath](args)
                    else:
                        raise
            prefix_enabled = False

            if not pointer.children:
                break

        return pointer, args
