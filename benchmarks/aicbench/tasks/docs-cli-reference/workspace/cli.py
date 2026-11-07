import argparse


def build_parser():
    parser = argparse.ArgumentParser(prog="inventory")
    commands = parser.add_subparsers(dest="command", required=True)
    import_command = commands.add_parser("import")
    import_command.add_argument("--path", required=True, help="CSV file to read")
    export_command = commands.add_parser("export")
    export_command.add_argument("--path", required=True, help="CSV file to write")
    export_command.add_argument("--overwrite", action="store_true", help="Replace an existing file")
    return parser


def main(argv=None):
    return build_parser().parse_args(argv)
