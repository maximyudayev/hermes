import os
import shutil
from pathlib import Path

def invert_directory_structure(source_root: str, dest_root: str, copy_files: bool = False):
    source_path = Path(source_root)
    dest_path = Path(dest_root)

    if not source_path.is_dir():
        print(f"Error: Source directory '{source_root}' not found.")
        return

    print(f"Starting inversion from '{source_path}' to '{dest_path}'.")
    print(f"Operation: {'Copying' if copy_files else 'Moving'} files.")

    # Create the destination root directory if it doesn't exist
    dest_path.mkdir(exist_ok=True)

    # Level 1: Iterate through unique folders (e.g., 'A', 'B', 'C')
    for unique_folder in source_path.iterdir():
        if not unique_folder.is_dir():
            continue

        # Level 2: Iterate through common folders (e.g., 'bytes_1', 'rate_10')
        for common_folder in unique_folder.iterdir():
            if not common_folder.is_dir():
                continue

            # Construct the new destination directory path
            # e.g., dest_root / 'bytes_1' / 'A'
            new_dest_dir = dest_path / common_folder.name / unique_folder.name
            
            # Create the new directory structure
            new_dest_dir.mkdir(parents=True, exist_ok=True)

            # Process each file within the common folder
            for file_path in common_folder.glob('*'):
                if file_path.is_file():
                    dest_file = new_dest_dir / file_path.name
                    
                    try:
                        if copy_files:
                            shutil.copy2(file_path, dest_file)
                            print(f"Copied '{file_path}' to '{dest_file}'")
                        else:
                            shutil.move(str(file_path), str(dest_file))
                            print(f"Moved '{file_path}' to '{dest_file}'")
                    except Exception as e:
                        print(f"Error processing '{file_path}': {e}")

    print("\nInversion complete.")


if __name__ == "__main__":
    current_file = os.path.dirname(os.path.realpath(__file__))
    source_directory = f"{current_file}/../data/latency/localhost"
    destination_directory = f"{current_file}/../data/latency/localhost_inverted"

    invert_directory_structure(
        source_root=source_directory, 
        dest_root=destination_directory,
        copy_files=True
    )

    # --- Verification (Optional) ---
    print("\n--- New structure in", destination_directory, "---")
    # This will print the contents of the newly created directory
    for path in sorted(Path(destination_directory).rglob('*')):
        indent = "  " * (len(path.parts) - len(Path(destination_directory).parts))
        print(f"{indent}{path.name}")
