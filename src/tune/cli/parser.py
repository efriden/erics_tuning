from argparse import ArgumentParser


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="tms", description="A tuning application.")

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser(
        name="visualizer",
        help="Start the tms visualizer",
        aliases=["viz", "vis"],
    )

    subparsers.add_parser(
        name="analyzer",
        help="Start the tms audio analyzer",
        aliases=["ana", "anal"],
    )

    return parser
