import pytest
import subprocess
from pathlib import Path

def test_embed_script():

    # Run the embed helper script
    command = ["./scripts/embed.sh", "./tests/files/100sec.wav", "./tests/output/"]
    print(f'running command: {" ".join(command)}')
    subprocess.run(command, check=True)

    # Specify the expected output files
    expected_output_files = ["./tests/output/100sec.wav.parquet"] 

    for file in expected_output_files:
        assert Path(file).exists()