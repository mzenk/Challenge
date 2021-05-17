"""
This script is meant to be executed for each container on the remote FeTS platforms,
from the FeTS-CLI (which does the metric calculations).
"""

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import time

# TODO use logging instead of prints -> how to sensibly combine with FeTS-CLI?

if __name__ == "__main__":

    print("Testing FeTS singularity image...")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "sif_file", type=str,
        help="Name of the container file you want to test. Should have the format 'teamXYZ.sif'"
    )
    parser.add_argument('-s', '--subject_id', type=str,
                        help='Subjext ID.')
    parser.add_argument('-t1', '--t1_path', type=str,
                        help='absolute path to t1 image.')
    parser.add_argument('-t1c', '--t1c_path', type=str,
                        help='absolute path to t1 post contrast image.')
    parser.add_argument('-t2', '--t2_path', type=str,
                        help='absolute path to t2 image.')
    parser.add_argument('-fl', '--fl_path', type=str,
                        help='absolute path to flair image.')
    parser.add_argument('-o', '--out_folder', type=str,
                        help='absolute path to output directory where the container will write all results, ')
    parser.add_argument(
        "--timeout", default=200, required=False, type=int,
        help="Time budget PER CASE in seconds. Evaluation will be stopped after the total timeout of timeout * n_cases."
    )

    args = parser.parse_args()

    TIME_PER_CASE = args.timeout   # seconds
    sif_file = args.sif_file
    subject_id = args.subject_id
    t1_path = Path(args.t1_path)
    t1c_path = Path(args.t1c_path)
    t2_path = Path(args.t2_path)
    fl_path = Path(args.fl_path)
    output_dir = Path(args.out_folder)

    container_indir = Path("/data")
    container_outdir = Path("/out_dir")

    # build singularity bind mount paths (to include only test case images without segmentation)
    # this will result in a very long bind path, unfortunately.
    bind_str = ""
    t1_path_container = container_indir / t1_path.name
    t1c_path_container = container_indir / t1c_path.name
    t2_path_container = container_indir / t2_path.name
    fl_path_container = container_indir / fl_path.name
    bind_str += (
        f"{t1_path}:{t1_path_container}:ro,"
        f"{t1c_path}:{t1c_path_container}:ro,"
        f"{t2_path}:{t2_path_container}:ro,"
        f"{fl_path}:{fl_path_container}:ro,"
    )
    assert "_seg.nii.gz" not in bind_str, "Container should not have access to segmentation files!"
    
    bind_str += f"{output_dir}:/{container_outdir}:rw"
    print(f"The bind path string is in total {len(bind_str)} characters long.")
    os.environ["SINGULARITY_BINDPATH"] = bind_str

    print("\nRunning container...")

    ret = ""
    try:
        start_time = time.monotonic()

        singularity_str = (
            f"singularity run -C --writable-tmpfs --net --network=none --nv"
            f" {sif_file}"
            f" -s {subject_id}"
            f" -t1 {t1_path_container}"
            f" -t1c {t1c_path_container}"
            f" -t2 {t2_path_container}"
            f" -fl {fl_path_container}"
            f" -o {container_outdir}"
        )
        # Alternatively, we could also use the -i -o interface and just bind one case into /data...
        
        print(singularity_str)
        ret = subprocess.run(
            shlex.split(singularity_str),
            timeout=TIME_PER_CASE,
            check=True
        )
        end_time = time.monotonic()
    except subprocess.TimeoutExpired:
        print(f"Timeout of {TIME_PER_CASE} reached."
              f" Aborting...")
        exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Running container failed:")
        raise e
        # I re-raise exceptions here, because they would indicate that something is wrong with the submission
    print(f"Execution time of the container: {end_time - start_time:0.2f} s")
