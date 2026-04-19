from hermes.cli import inject_env_vars
import sys


def parse_config_file(
    in_file: str,
    out_file: str,
):
    with open(in_file, "r") as f:
        config_str = f.read()
        config_str = inject_env_vars(config_str)

    with open(out_file, "w") as f:
        f.write(config_str)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python dist_utils.py <input_file_path> <output_file_path>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    parse_config_file(input_file, output_file)
