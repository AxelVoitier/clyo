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
    from collections.abc import Callable, Iterable, Iterator, Mapping
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
from prompt_toolkit import ANSI, PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import (Completer, Completion, FuzzyCompleter,
                                       NestedCompleter, WordCompleter)
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.output import ColorDepth
from rich import print as rprint
from rich.text import Text
from typer import rich_utils
from typer.main import get_command

# Local imports


DEBUG = False


def print_in_terminal(*args: Any, **kwargs: Any) -> None:
    if not DEBUG:
        return

    from prompt_toolkit.application import run_in_terminal

    def _() -> None:
        print(*args, **kwargs)

    run_in_terminal(_)
    print(*args, **kwargs)


def rich_to_ptk(*renderables: RenderableType) -> ANSI:
    console = rich_utils._get_rich_console()
    console.begin_capture()

    for renderable in renderables:
        console.print(renderable, end='')

    rendered = console.end_capture()
    return ANSI(rendered.strip())


class TreeCompleter(Completer):

    def __init__(
        self,
        command_tree: CommandTree,
        current_completer: Completer | None = None
    ) -> None:
        self._tree = command_tree
        self._current_completer = current_completer or self._tree.root_command.completer

    @property
    def current_completer(self) -> Completer:
        return self._current_completer

    @current_completer.setter
    def current_completer(self, completer: Completer) -> None:
        self._current_completer = completer

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent
    ) -> Iterator[Completion]:
        # print_in_terminal(
        #     f'\n---------\nNew completion: |{document.text}|, |{document.text_before_cursor}|, '
        #     f'{complete_event=}, '
        #     f'complete_state={self._tree.current_prompt.default_buffer.complete_state}, '
        #     f'cursor_pos={document.cursor_position}'
        # )

        command, _, command_len = self._tree.get_command(document.text, partial=True)
        new_pos = document.cursor_position - command_len
        print_in_terminal(f'\nCommand is: {command.path}, len={command_len}, {new_pos=}', )
        if command_len and not new_pos and (document.text[document.cursor_position - 1] != '/'):
            return

        document = Document(
            document.text[command_len:],
            cursor_position=new_pos
        )
        yield from command.completer.get_completions(document, complete_event)


class AutoTreeCompleter(TreeCompleter):

    @property
    def current_completer(self) -> Completer:
        return self._tree.current_command.completer

    @current_completer.setter
    def current_completer(self, completer: Completer) -> None:
        raise ValueError('Cannot set a current completer on an AutoTreeCompleter')


class CommandCompleter(WordCompleter):

    def __init__(
        self,
        options_with_extra: Mapping[str, NestedCompleterWithExtra.Option],
        *args: Any,
        path: str,
        arguments: Iterable[NestedCompleterWithExtra.Argument] | None = None,
        **kwargs: Any,
    ) -> None:
        self._display_dict: dict[str, AnyFormattedText] = {}
        self._meta_dict: dict[str, AnyFormattedText] = {}
        self._hidden: dict[str, Completer | None] = {}
        options: dict[str, Completer | None] = {}
        self._path = path

        for name, (option, display, meta, opt_kwargs, is_group) in options_with_extra.items():
            # if is_group:
            #     name += '/'
            # else:
            #     name += ' '

            if opt_kwargs.get('hidden', False):
                self._hidden[name] = option
            else:
                options[name] = option
                self._display_dict[name] = display
                self._meta_dict[name] = meta

        self._arguments: list[Completion] = []
        if arguments:
            for text, display, meta, arg_kwargs in arguments:
                if arg_kwargs.get('hidden', False):
                    continue

                self._arguments.append(Completion(
                    text=text,
                    start_position=0,
                    display=display,
                    display_meta=meta,
                ))

        super().__init__(
            *args,
            words=list(options.keys()),
            display_dict=self._display_dict,
            meta_dict=self._meta_dict,
            **kwargs
        )

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent
    ) -> Iterator[Completion]:
        text = document.text_before_cursor.lstrip()
        print_in_terminal(f'\nFor path {self._path}: |{document.text=}| ; |{text=}|')

        yield from super().get_completions(document, complete_event)

        # if not document.text:
        nargs = len([term for term in text.split() if '=' not in term])
        print_in_terminal(f'\n{nargs=}')
        for arg in self._arguments[nargs:]:
            print_in_terminal('yielding arg', arg)
            yield arg


class NestedCompleterWithExtra(NestedCompleter):

    if TYPE_CHECKING:
        Option: TypeAlias = tuple[
            Completer | None,  # Option
            AnyFormattedText,  # Display
            AnyFormattedText,  # Meta
            dict[str, Any],  # Option kwargs
            bool,  # Is group
        ]
        Argument: TypeAlias = tuple[
            str,  # Text
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

        for name, (option, display, meta, opt_kwargs, _) in options_with_extra.items():
            if opt_kwargs.get('hidden', False):
                self._hidden[name] = option
            else:
                options[name] = option
                self._display_dict[name] = display
                self._meta_dict[name] = meta

        self._arguments: list[Completion] = []
        if arguments:
            for text, display, meta, arg_kwargs in arguments:
                if arg_kwargs.get('hidden', False):
                    continue

                self._arguments.append(Completion(
                    text=text,
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
                bool(node.children),
            )

        # self.completer = NestedCompleterWithExtra(dict(completion_dict))
        self.completer = CommandCompleter(dict(completion_dict), path=str(self.path))

    def _make_command_completer(self) -> None:  # noqa: C901
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
                        metavar_text.append(f'[{range_str}]')
            except AttributeError:
                # click.types._NumberRangeBase is only in Click 8x onwards
                pass
            metavar_text.append(' ')

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
                        False,
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
                    param.human_readable_name,
                    display,
                    meta_str,
                    dict(hidden=hidden),
                ))

        # self.completer = NestedCompleterWithExtra(completion_dict, arguments=argument_list)
        self.completer = CommandCompleter(
            completion_dict, arguments=argument_list, path=str(self.path))


class CommandTree:

    if TYPE_CHECKING:
        Prefix: TypeAlias = Callable[[str, int, bool], tuple[Node, str, int]]

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
        self.current_prompt: PromptSession[str] | None = None
        self.use_fuzzy_completer = True

        self._prefixes: dict[str, CommandTree.Prefix] = {}
        self.add_prefix('help', self._help_prefix)
        self.add_prefix('?', self._help_prefix)

    @property
    def path(self) -> Path:
        return self._pointer.path

    @path.setter
    def path(self, path: str | Path) -> None:
        command, args = self[str(path)]

        if args:
            raise ValueError(f'Cannot set a path that contains arguments: {args}')
        if not command.children:
            raise ValueError(f'Cannot set a path that is a leaf command: {command.path}')

        self.goto(command)

    def goto(self, command: Node) -> None:
        self._pointer = command

    @property
    def current_command(self) -> Node:
        return self._pointer

    @property
    def root_command(self) -> Node:
        return self._root

    @property
    def at_root(self) -> bool:
        return (self.path == self.ROOT_PATH)

    @property
    def completer(self) -> Completer:
        return self._completer

    @completer.setter
    def completer(self, value: Completer) -> None:
        self._completer = value
        if self.current_prompt:
            self.current_prompt.completer = value

    @property
    def use_fuzzy_completer(self) -> bool:
        return isinstance(self._completer, FuzzyCompleter)

    @use_fuzzy_completer.setter
    def use_fuzzy_completer(self, value: bool) -> None:
        if value:
            self.completer = FuzzyCompleter(AutoTreeCompleter(self))
        else:
            self.completer = AutoTreeCompleter(self)

    def add_prefix(self, name: str, callback: CommandTree.Prefix) -> None:
        self._prefixes[name] = callback

    def _help_prefix(self, prompt: str, command_len: int, partial: bool) -> tuple[Node, str, int]:
        remain = prompt[command_len:]
        if remain.strip():
            command, _, new_command_len = self.get_command(
                remain, prefix_enabled=False, partial=partial)
        else:
            command = self._pointer
            new_command_len = 0

        return command, '--help', (command_len + new_command_len)

    def __getitem__(self, name: str) -> tuple[Node, str]:
        return self.get_command(name, prefix_enabled=True)[:2]

    def get_command(  # noqa: C901
        self,
        prompt: str,
        prefix_enabled: bool = True,
        partial: bool = False,
    ) -> tuple[Node, str, int]:
        '''Parse a user prompt input into a command and its args.

        Supports hiearchy navigation UNIX-like. But also supports to replace
        the "/" with " ".

        Supports comments with "#".

        Supports prefixes (special commands) added with add_prefix() (defaults are "help" and "?").

        Supports getting partial answer (ie. avoid failing on KeyError) when the last part of the
        command is unknown, which typically happens in interactive session as user type it in.

        Args:
            prompt: The user input. Or whatever command path if you use it programmatically.
            prefix_enabled (optional, defaults to True): If True, authorise the input to have one of
              the declared prefixes.
            partial (optional, defaults to False): If True, will not raise KeyError if the last part
              is not resolved. Instead, it will return the command that has been resolved so far.

        Raises:
            KeyError:
                When the specified command is unknown.

        Returns:
            Returns a tuple with three elements:
                - First: The resolved Command object
                - Second: The arguments to the command (or, when using partial, the unresolved part)
                - Third: The length of the command (including the separating space(s) if there are
                  args, but not including it(them) if there are no args)
        '''
        # Handle comments
        if '#' in prompt:
            prompt = prompt[:prompt.index('#')]

        # We need to keep a reference to the original string.
        original = prompt
        # prompt will be our working/running string as we iterate through the command
        prompt = prompt.strip().replace(' ', '/')
        # command_len represents delimitation index between command and args in the original string
        command_len = 0

        # Init pointer. If prompt starts with /, then we get the root pointer.
        # Else, it's the current pointer.
        pointer = self._pointer
        if original.lstrip().startswith('/'):
            pointer = self._root
            command_len = original.index('/') + 1
            prompt = prompt[1:]

        # Loop to parse the command part
        while prompt:
            previous_command_len = command_len  # Save it for partial case
            fields = prompt.split('/', maxsplit=1)
            command = fields.pop(0)

            # If we only have / (or even possibly a space in the original),
            # then the line updating command_len just below would not catch it
            # and wouldn't increment it correctly.
            if prompt[0] == '/':
                command_len += 1

            # If index fails (ValueError), our algo is wrong, and it's a bug
            command_len = original.index(command, command_len) + len(command)

            # If split did actually swallow a real /, then we need to account for it
            if command and (len(original) > command_len) and (original[command_len] == '/'):
                command_len += 1

            # The rest remaining to process in next iteration
            prompt = fields.pop() if fields else ''

            # Pointer advancement, and special cases of ., .., /, '', and prefixes
            if command == '..':
                pointer = pointer.parent if pointer.parent else pointer
            elif command and (command != '.'):  # If not, do nothing. Handles case of just '/'.
                try:
                    pointer = pointer.children[command]
                except KeyError:
                    if prefix_enabled and (command in self._prefixes):
                        if (len(original) > command_len) and (original[command_len] != ' '):
                            # Lack space after prefix. Disregard partial here.
                            raise
                        # Delegate prefix processing to its callback.
                        # This is likely to call get_command() again to parse
                        # the rest of the prompt.
                        return self._prefixes[command](original, command_len, partial)
                    elif partial:
                        # Case of partially written command (interactive user input).
                        # We still want to return the valid command portion we got so far.
                        command_len = previous_command_len
                        break
                    else:
                        raise

            # We had at least one valid command, prefixes are therefore no longer possible
            prefix_enabled = False

            # No more command subpath down in that hierarchy. Exit loop with pointer representing
            # the actual full (leaf) command, and with command_len pointing to the index
            # position in the original string where arguments starts (almost).
            if not pointer.children:
                break

        # print_in_terminal(
        #     'get_command', pointer.path, original, command_len, original[command_len:])

        # Consume / at the end of the command part
        for char in original[command_len:]:
            if char == '/':
                command_len += 1
            elif char == ' ':
                break
            elif partial:
                # Case of partially written command using / as separator
                break
            else:
                # This case corresponds to args separated from the command using /
                raise KeyError(original[command_len:])

        args = original[command_len:].strip()
        if args:
            # Count the separating space(s) only if we do have args
            command_len = original.index(args, command_len)

        return pointer, args, command_len

    def make_prompt_session(self, **prompt_kwargs: Any) -> PromptSession[str]:
        prompt_kwargs.setdefault('message', self.prompt_message)
        prompt_kwargs.setdefault('color_depth', ColorDepth.TRUE_COLOR)
        prompt_kwargs.setdefault('completer', self.completer)
        prompt_kwargs.setdefault('auto_suggest', AutoSuggestFromHistory())
        prompt_kwargs.setdefault('mouse_support', True)
        # prompt_kwargs.setdefault('enable_system_prompt', True)

        return PromptSession[str](**prompt_kwargs)

    def prompt_message(self) -> AnyFormattedText:
        return [
            ('#00aa00', '['),
            ('ansibrightcyan', str(self.path)),
            ('#00aa00', '] ')
        ]

    def repl(self, session: PromptSession[str], **prompt_kwargs: Any) -> None:
        self.current_prompt = session
        try:
            input = session.prompt(**prompt_kwargs)
        finally:
            self.current_prompt = None

        try:
            command, args = self[input]
        except KeyError as ex:
            rprint('[red]Command not found:[/]', ex.args[0], file=sys.stderr)
            return

        if command.children and not args:
            self.goto(command)
        else:
            command.exec(args)
