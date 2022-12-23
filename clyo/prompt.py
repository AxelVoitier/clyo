# Copyright (c) 2022 Contributors as noted in the AUTHORS file
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# System imports
from __future__ import annotations
from dataclasses import dataclass, field
from itertools import chain
from pathlib import Path

# Third-party imports
import click
import typer
from click.parser import split_opt
from prompt_toolkit.completion import (
    NestedCompleter, Completer, FuzzyCompleter, WordCompleter,
    Completion,
)
from prompt_toolkit.document import Document
from typer.main import get_command

# Local imports


DEBUG = True


def print_in_terminal(*args, **kwargs):
    if not DEBUG:
        return

    from prompt_toolkit.application import run_in_terminal

    def _():
        print(*args, **kwargs)

    run_in_terminal(_)


class RootCompleter(Completer):

    def __init__(self, level, root):
        self._level = level
        self._root = root

    def get_completions(self, document, complete_event):
        # print_in_terminal(f'\n---------\nNew completion: |{document.text}|')
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

    def __init__(self, options_with_extra, *args, arguments=None, **kwargs):
        self._display_dict = {}
        self._meta_dict = {}
        self._hidden = {}
        options = {}

        for name, (option, display, meta, opt_kwargs) in options_with_extra.items():
            if opt_kwargs.get('hidden', False):
                self._hidden[name] = option
            else:
                options[name] = option
                self._display_dict[name] = display
                self._meta_dict[name] = meta

        self._arguments = []
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

    def get_completions(self, document, complete_event):
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
            remaining_text = terms[-1]
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


class CommandTree:

    ROOT_PATH = Path('/')

    @dataclass
    class Node:
        name: str
        command: click.Command = None
        completer: Completer = None
        children: dict = field(default_factory=dict)
        parent: Node = None
        path: Path = field(init=False)

        def __post_init__(self):
            if self.parent:
                self.path = self.parent.path / self.name
            else:
                self.path = CommandTree.ROOT_PATH / self.name

        @property
        def _options_trans(self):
            parser = self.command.make_parser(click.get_current_context())
            return {
                split_opt(opt)[1]: opt
                for opt in chain(parser._short_opt.keys(), parser._long_opt.keys())
            }

        def make_args(self, args_string):
            args = None
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

    def __init__(self, cli):
        self._cli = cli
        root_command = self._cli
        if isinstance(root_command, typer.Typer):
            root_command = get_command(root_command)
        self._root = self.Node(
            name='',
            command=root_command,
            children=dict(self._make_model(root_command)),
        )
        self._make_group_completer(self._root)
        self._pointer = self._root
        self._parents = []

    @property
    def path(self):
        return self._pointer.path

    def _make_group_completer(self, node):
        def _completion_dict(base):
            for node in base.children.values():
                yield node.name, (
                    node.completer,
                    None,
                    (node.command.help or ' ').splitlines()[0].strip(),
                    dict(hidden=node.command.hidden),
                )

        node.completer = NestedCompleterWithExtra(dict(_completion_dict(node)))

    def _make_command_completer(self, node):
        completion_dict = {}
        argument_list = []
        for param in node.command.params:
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

                    completion_dict[opt_name] = (
                        None,
                        None,
                        (param.help or ' ').splitlines()[0].strip(),
                        dict(hidden=param.hidden),
                    )

            elif isinstance(param, click.Argument):
                argument_list.append((
                    f'<{param.human_readable_name}>',
                    (param.help or ' ').splitlines()[0].strip(),
                    dict(hidden=param.hidden),
                ))

        node.completer = NestedCompleterWithExtra(completion_dict, arguments=argument_list)

    def _make_model(self, command, parent=None):
        for subcommand in command.commands.values():
            node = self.Node(
                name=subcommand.name,
                command=subcommand,
                parent=parent,
            )
            if isinstance(subcommand, click.Group):
                node.children = dict(self._make_model(subcommand, node))
                self._make_group_completer(node)
            else:
                self._make_command_completer(node)

            yield node.name, node

    @property
    def completer(self):
        return FuzzyCompleter(RootCompleter(self._pointer.completer, self._root))
        # return RootCompleter(self._pointer.completer, self._root)

    @property
    def at_root(self):
        return (self.path == self.ROOT_PATH)

    def __getitem__(self, name):
        pointer = self._pointer
        if name.lstrip().startswith('/'):
            pointer = self._root

        remain = name.replace('/', ' ').strip()
        while remain:
            fields = remain.split(' ', maxsplit=1)
            subpath = fields.pop(0)
            remain = fields.pop() if fields else ''

            if not subpath:
                continue

            if subpath == '..':
                pointer = pointer.parent if pointer.parent else pointer
            else:
                pointer = pointer.children[subpath]

            if not pointer.children:
                break

        return pointer, remain
