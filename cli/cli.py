# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import os
import sys
import argparse

from . import ansi, i18n
from .ansi import Ansi, paint

VERSION = "4.0.1.3"


class _Formatter(argparse.RawDescriptionHelpFormatter):
    pass


def _add_global_opts(parser):
    parser.add_argument("--lang", metavar="<en|ch_zn>",
                        help=i18n.t("cli.opt_lang"))
    parser.add_argument("--color", choices=["auto", "always", "never"],
                        default="auto", help=i18n.t("cli.opt_color"))


def _add_download_opts(parser):
    parser.add_argument("url", nargs="?", help=i18n.t("opt.url"))
    parser.add_argument("-o", "--output", help=i18n.t("opt.output"))
    parser.add_argument("-f", "--filename", help=i18n.t("opt.filename"))
    parser.add_argument("-j", "--jobs", type=int, default=None,
                        help=i18n.t("opt.jobs"))
    parser.add_argument("-s", "--chunk-size", type=float, default=None,
                        help=i18n.t("opt.chunk_size"))
    parser.add_argument("--cache", type=float, default=None,
                        help=i18n.t("opt.cache"))
    parser.add_argument("--limit", type=float, default=0.0,
                        help=i18n.t("opt.limit"))
    parser.add_argument("--timeout", type=float, default=None,
                        help=i18n.t("opt.timeout"))
    parser.add_argument("-H", "--header", action="append", default=[],
                        help=i18n.t("opt.header"))
    parser.add_argument("--header-json", default="",
                        help=i18n.t("opt.header_json"))
    parser.add_argument("--no-ssl-check", action="store_true",
                        help=i18n.t("opt.no_ssl_check"))
    parser.add_argument("--backend", default="auto",
                        choices=["auto", "requests", "curl"],
                        help=i18n.t("opt.backend"))
    parser.add_argument("--run", choices=["open", "shutdown"], default="",
                        help=i18n.t("opt.run"))
    parser.add_argument("--speed-unit", default="",
                        choices=["", "MB/s", "MiB/s", "Mbps"],
                        help=i18n.t("opt.speed_unit"))
    parser.add_argument("--json", action="store_true",
                        help=i18n.t("opt.json"))


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="nodanium",
        add_help=False,
        formatter_class=_Formatter,
    )
    parser.add_argument("-h", "--help", action="store_true",
                        help=i18n.t("cli.opt_help"))
    parser.add_argument("-v", "--version", action="store_true",
                        help=i18n.t("cli.opt_version"))
    _add_global_opts(parser)

    sub = parser.add_subparsers(dest="command")
    dl = sub.add_parser("download", add_help=False,
                        help=i18n.t("cli.cmd_download"))
    dl.add_argument("-h", "--help", action="store_true")
    _add_global_opts(dl)
    _add_download_opts(dl)
    return parser, {"download": dl}


def _section(title):
    print(paint(title + ":", Ansi.BOLD, Ansi.MAGENTA))


def _opt(flag, desc, value=""):
    flag_txt = paint(flag, Ansi.YELLOW)
    if value:
        flag_txt += " " + paint(value, Ansi.GRAY)
    print(f"  {flag_txt:<34} {desc}")


def _print_version():
    print(paint(f"{i18n.t('cli.app_title')} v{VERSION}", Ansi.BOLD, Ansi.CYAN))
    print("  " + paint(i18n.t("welcome.version_line", version=VERSION,
                             lang=i18n.current()), Ansi.DIM))


def _cmd(name, args, desc, subs=()):
    line = "  " + paint(name, Ansi.BOLD, Ansi.CYAN)
    if args:
        line += " " + paint(args, Ansi.GRAY)
    print(line)
    print("      " + desc)
    for s in subs:
        print("      " + paint(s, Ansi.DIM))


def _print_help():
    print(paint(f"{i18n.t('cli.app_title')} v{VERSION}", Ansi.BOLD, Ansi.CYAN))
    

    _section(i18n.t("cli.usage"))
    print("  " + paint(i18n.t("cli.usage_line"), Ansi.WHITE))
    print("  " + paint("nodanium <command> [options]", Ansi.GRAY))
   

    _section(i18n.t("cli.commands"))
    _cmd("download", "<url> [options]", i18n.t("cli.cmd_download"),
         ("nodanium download --help",))
    _cmd("tui", "", i18n.t("cli.cmd_tui"))
    _cmd("help", "[command]", i18n.t("cli.cmd_help"))
    _cmd("version", "", i18n.t("cli.opt_version"))
   

    _section(i18n.t("cli.global_options"))
    _opt("-h, --help", i18n.t("cli.opt_help"))
    _opt("-v, --version", i18n.t("cli.opt_version"))
    _opt("--lang", i18n.t("cli.opt_lang"), "<en|ch_zn>")
    _opt("--color", i18n.t("cli.opt_color"), "<auto|always|never>")
  

    
   

    _section(i18n.t("cli.examples"))
    
    print("  " + paint(i18n.t(f"cli.example_3"), Ansi.DIM))
  

   

    _section(i18n.t("cli.exit_section"))
    print("  " + i18n.t("cli.interrupt_help"))
    print("  " + paint(i18n.t("cli.resume_hint"), Ansi.DIM))
  

    _section(i18n.t("cli.exitcodes"))
    _opt("0", i18n.t("cli.exit_ok"))
    _opt("1", i18n.t("cli.exit_fail"))
    _opt("2", i18n.t("cli.exit_usage"))
    _opt("3", i18n.t("cli.exit_noinfo"))
    _opt("4", i18n.t("cli.exit_nospace"))
    _opt("130", i18n.t("cli.exit_abort"))
   
    print("  " + paint(i18n.t("cli.gui_hint"), Ansi.DIM))


def _print_download_help():
    print(paint(f"{i18n.t('cli.app_title')} v{VERSION}", Ansi.BOLD, Ansi.CYAN))

    _section(i18n.t("cli.usage"))
    print("  " + paint("nodanium download <url> [options]", Ansi.WHITE))
   
    _section(i18n.t("cli.download_options"))
    _opt("<url>", i18n.t("opt.url"))
    _opt("-o, --output", i18n.t("opt.output"), "<dir>")
    _opt("-f, --filename", i18n.t("opt.filename"), "<name>")
    _opt("-j, --jobs", i18n.t("opt.jobs"), "<N>")
    _opt("-s, --chunk-size", i18n.t("opt.chunk_size"), "<MB>")
    _opt("--cache", i18n.t("opt.cache"), "<MB>")
    _opt("--limit", i18n.t("opt.limit"), "<KB/s>")
    _opt("--timeout", i18n.t("opt.timeout"), "<sec>")
    _opt("-H, --header", i18n.t("opt.header"), "\"K: V\"")
    _opt("--header-json", i18n.t("opt.header_json"), "<json>")
    _opt("--no-ssl-check", i18n.t("opt.no_ssl_check"))
    _opt("--backend", i18n.t("opt.backend"), "<auto|requests|curl>")
    _opt("--run", i18n.t("opt.run"), "<open|shutdown>")
    _opt("--speed-unit", i18n.t("opt.speed_unit"), "<MB/s|MiB/s|Mbps>")
    _opt("--json", i18n.t("opt.json"))

    _section(i18n.t("cli.global_options"))
    _opt("--lang", i18n.t("cli.opt_lang"), "<en|ch_zn>")
    _opt("--color", i18n.t("cli.opt_color"), "<auto|always|never>")
  
    _section(i18n.t("cli.examples"))
    for key in ("example_1", "example_2", "example_3"):
        print("  " + paint(i18n.t(f"cli.{key}"), Ansi.DIM))
   
    _section(i18n.t("cli.exit_section"))
    print("  " + i18n.t("cli.interrupt_help"))


def _print_welcome_banner():
    if not sys.stdout.isatty():
        return
    print(paint(f"{i18n.t('cli.app_title')} v{VERSION}", Ansi.BOLD, Ansi.CYAN))
    print()


def _print_welcome():

    if not sys.stdout.isatty():
        return
    try:
        width = min(os.get_terminal_size().columns, 72)
    except Exception:
        width = 72
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")
    logo = [
        " _   _           _             _                 ",
        "| \\ | | ___   __| | __ _ _ __ (_)_   _ _ __ ___  ",
        "|  \\| |/ _ \\ / _` |/ _` | '_ \\| | | | | '_ ` _ \\ ",
        "| |\\  | (_) | (_| | (_| | | | | | |_| | | | | | |",
        "|_| \\_|\\___/ \\__,_|\\__,_|_| |_|_|\\__,_|_| |_| |_|",
    ]
    accent = [Ansi.CYAN, Ansi.CYAN, Ansi.BLUE, Ansi.BLUE, Ansi.MAGENTA]
   
    for text, color in zip(logo, accent):
        print(paint(text, Ansi.BOLD, color))
    
    print("  " + paint(i18n.t("welcome.tagline"), Ansi.BOLD, Ansi.WHITE))
    print("  " + paint(
        i18n.t("welcome.version_line", version=VERSION,
               lang=i18n.current()), Ansi.DIM))
    print(paint("  " + "-" * (width - 2), Ansi.GRAY))
    print("  " + paint("› ", Ansi.GREEN) + i18n.t("welcome.hint_download"))
    print("  " + paint("› ", Ansi.GREEN) + i18n.t("welcome.hint_help"))
    print("  " + paint("› ", Ansi.GREEN) + i18n.t("welcome.hint_lang"))
    print(paint("  " + "-" * (width - 2), Ansi.GRAY))
   


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    argv = [a for a in argv if a != ""]  

    pre_lang = ""
    pre_color = "auto"
    for i, a in enumerate(argv):
        if a == "--lang" and i + 1 < len(argv):
            pre_lang = argv[i + 1]
        elif a.startswith("--lang="):
            pre_lang = a.split("=", 1)[1]
        elif a == "--color" and i + 1 < len(argv):
            pre_color = argv[i + 1]
        elif a.startswith("--color="):
            pre_color = a.split("=", 1)[1]
    i18n.load(pre_lang)
    ansi.set_mode(pre_color)

    parser, _ = _build_parser()


    command = ""
    skip = False
    for a in argv:
        if skip:
            skip = False
            continue
        if a in ("--lang", "--color"):
            skip = True
            continue
        if a.startswith("-"):
            continue
        command = a
        break

    if not command:
        if any(a in ("-v", "--version", "version") for a in argv):
            _print_welcome()
            
            return 0
        _print_welcome()
        _print_help()
        return 0

    if command in ("help",):
        _print_welcome()
        if any(a == "download" for a in argv):
            _print_download_help()
        else:
            _print_help()
        return 0

    if command in ("-v", "--version", "version"):
        _print_welcome()
        return 0

    if command == "tui":
        from . import tui
        return tui.run_tui()

    if command != "download":
        print(paint(i18n.t("error.unknown_command", cmd=command), Ansi.RED))
        return 2

    if any(a in ("-h", "--help") for a in argv):
        _print_welcome()
        _print_download_help()
        return 0

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2
    i18n.load(args.lang or pre_lang)
    ansi.set_mode(args.color or pre_color)

    if getattr(args, "help", False) or not args.url:
        _print_help()
        return 0

    from . import download
    _print_welcome()
    return download.run_download(args)


if __name__ == "__main__":
    sys.exit(main())
