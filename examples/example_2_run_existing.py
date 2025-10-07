"""
Example 2: Run with Existing Resources

This example shows how to run workitems when you ALREADY have:
- An existing bucket
- An existing AppBundle with alias
- An existing Activity with alias
"""

import os
import sys

# Add parent directory to path to import from main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation_workflow.main import DesignAutomationWorkflow
from dotenv import load_dotenv

load_dotenv()


def run_with_existing_resources(
    bucket_key: str,
    activity_id: str,
    alias: str,
    input_file_path: str,
    max_wait_time: int = 300,
    poll_interval: int = 10,
    download_result: bool = True,
):
    """
    Run a workitem using existing bucket, AppBundle, and Activity

    This is much faster than Example 1 because we skip all the setup steps

    Args:
        bucket_key: Existing bucket key from Example 1 (e.g., "testb1d396757f174640", "revitbucketf3a1b2c4")
        activity_id: Existing Activity ID (e.g., "DeleteWallsActivity", "ProcessWallsActivity")
        alias: Activity alias (e.g., "test", "prod", "dev", "staging")
        input_file_path: Path to input Revit file (e.g., "files/DeleteWalls.rvt", "files/MyModel.rvt")
        max_wait_time: Maximum seconds to wait for completion (default: 300)
        poll_interval: Seconds between status checks (default: 10)
        download_result: Auto-download result when done (default: True)

    Returns:
        Dictionary with workitem results
    """
    print("=" * 80)
    print("EXAMPLE 2: RUN WITH EXISTING RESOURCES")
    print("=" * 80)

    print("\nUsing Existing Resources:")
    print(f"  Bucket: {bucket_key}")
    print(f"  Activity: {activity_id}")
    print(f"  Alias: {alias}")
    print(f"  Input File: {input_file_path}")

    # Initialize workflow with existing bucket
    workflow = DesignAutomationWorkflow(bucket_key=bucket_key)

    # Run the workitem
    print("\n" + "=" * 80)
    print("RUNNING WORKITEM")
    print("=" * 80)

    if not os.path.exists(input_file_path):
        print(f"Error: Input file not found: {input_file_path}")
        return

    workitem_result = workflow.run_workitem(
        input_file_path=input_file_path,
        activity_id=activity_id,
        alias=alias,
        max_wait_time=max_wait_time,
        poll_interval=poll_interval,
        download_result=download_result,
    )

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    print(f"\nWorkItem ID: {workitem_result['workitem_id']}")
    print(f"Status: {workitem_result['status']}")
    print(f"Processing Time: {workitem_result['elapsed_time']} seconds")

    if workitem_result["status"] == "success":
        print("\n🎉 SUCCESS!")
        print(f"\nInput:  {input_file_path}")
        print(
            f"Output: {workitem_result.get('downloaded_file_path', 'Not downloaded')}"
        )

        if "downloaded_file_size" in workitem_result:
            print(
                f"\nOutput file size: {workitem_result['downloaded_file_size']:,} bytes"
            )

        print("\nWorkitem completed successfully!")

    elif workitem_result["status"] == "failed":
        print("\nWORKITEM FAILED")
        print(f"Report URL: {workitem_result.get('report_url', 'N/A')}")

    elif workitem_result["status"] == "timeout":
        print("\nTIMEOUT")
        print(
            f"Workitem didn't complete within {workitem_result['elapsed_time']} seconds"
        )

    print("\n" + "=" * 80)

    return workitem_result


def run_multiple_files(
    bucket_key: str,
    activity_id: str,
    alias: str,
    input_files: list[str],
    max_wait_time: int = 300,
    poll_interval: int = 10,
):
    """
    Process multiple files in batch using existing resources

    This example shows how to process multiple files efficiently

    Args:
        bucket_key: Existing bucket key (e.g., "testb1d396757f174640")
        activity_id: Existing Activity ID (e.g., "DeleteWallsActivity")
        alias: Activity alias (e.g., "test", "prod", "dev")
        input_files: List of file paths to process (e.g., ["files/Model1.rvt", "files/Model2.rvt"])
        max_wait_time: Maximum seconds to wait per file (default: 300)
        poll_interval: Seconds between status checks (default: 10)

    Returns:
        List of result dictionaries for each file
    """
    print("=" * 80)
    print("BATCH PROCESSING EXAMPLE")
    print("=" * 80)

    print(f"\nProcessing {len(input_files)} file(s)...")
    print(f"Bucket: {bucket_key}")
    print(f"Activity: {activity_id} (alias: {alias})")

    workflow = DesignAutomationWorkflow(bucket_key=bucket_key)
    results = []

    for i, file_path in enumerate(input_files, 1):
        print(f"\n{'=' * 80}")
        print(f"FILE {i}/{len(input_files)}: {file_path}")
        print(f"{'=' * 80}")

        if not os.path.exists(file_path):
            print(f"Warning: File not found, skipping: {file_path}")
            results.append(
                {"file": file_path, "status": "skipped", "reason": "File not found"}
            )
            continue

        try:
            result = workflow.run_workitem(
                input_file_path=file_path,
                activity_id=activity_id,
                alias=alias,
                max_wait_time=max_wait_time,
                poll_interval=poll_interval,
                download_result=True,
            )

            results.append(
                {
                    "file": file_path,
                    "status": result["status"],
                    "workitem_id": result["workitem_id"],
                    "elapsed_time": result["elapsed_time"],
                    "output_file": result.get("downloaded_file_path"),
                }
            )

            if result["status"] == "success":
                print(
                    f"{file_path} processed successfully ({result['elapsed_time']}s)"
                )
            else:
                print(f"{file_path} failed")

        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            results.append({"file": file_path, "status": "error", "error": str(e)})

    print("\n" + "=" * 80)
    print("BATCH PROCESSING SUMMARY")
    print("=" * 80)

    successful = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] in ["failed", "error"])
    skipped = sum(1 for r in results if r["status"] == "skipped")

    print(f"\nTotal Files: {len(input_files)}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Skipped: {skipped}")

    print("\nDetailed Results:")
    for r in results:
        status_icon = (
            "OK"
            if r["status"] == "success"
            else "FAIL"
            if r["status"] == "failed"
            else "SKIP"
        )
        print(f"  {status_icon} {r['file']}: {r['status']}")
        if "elapsed_time" in r:
            print(f"      Time: {r['elapsed_time']}s")
        if "output_file" in r:
            print(f"      Output: {r['output_file']}")

    print("\n" + "=" * 80)

    return results


def download_previous_result(bucket_key: str, output_object_key: str, output_path: str):
    """
    Download a result file from a previous workitem

    Use this when:
    - You lost the downloaded file
    - You want to re-download a previous result
    - You ran a workitem but didn't download it

    Args:
        bucket_key: Bucket containing the file (e.g., "testb1d396757f174640")
        output_object_key: Object key from workitem result (e.g., "result_1208da84-e76a-4007-a20e-23eeb8b15540.rvt")
        output_path: Where to save the file (e.g., "files/downloaded_result.rvt", "files/my_custom_name.rvt")

    Returns:
        Dictionary with file_path and file_size
    """
    print("=" * 80)
    print("DOWNLOAD PREVIOUS RESULT")
    print("=" * 80)

    print(f"\nDownloading from bucket: {bucket_key}")
    print(f"Object key: {output_object_key}")
    print(f"Save to: {output_path}")


    workflow = DesignAutomationWorkflow(bucket_key=bucket_key)

    try:
        result = workflow.download_result_file(
            object_key=output_object_key, local_path=output_path
        )

        print("\nDownload complete!")
        print(f"File path: {result['file_path']}")
        print(f"File size: {result['file_size']:,} bytes")

        return result

    except Exception as e:
        print(f"\nDownload failed: {e}")
        print("\nPossible reasons:")
        print("  - File doesn't exist in bucket")
        print("  - File was deleted (transient buckets auto-delete after 24h)")
        print("  - Incorrect bucket_key or object_key")
        return None


if __name__ == "__main__":
    """
    Choose which example to run
    """
    print("\nAvailable examples:")
    print("1. Run single workitem with existing resources")
    print("2. Batch process multiple files")
    print("3. Download previous result")

    # results = run_multiple_files(
    #     bucket_key="testb1d396757f174640",
    #     activity_id="DeleteWallsActivity",
    #     alias="test",
    #     input_files=[
    #         "files/DeleteWalls.rvt",
    #         "files/Model1.rvt",
    #         "files/Model2.rvt"
    #     ]
    # )

    # result = download_previous_result(
    #     bucket_key="testb1d396757f174640",
    #     output_object_key="result_1208da84-e76a-4007-a20e-23eeb8b15540.rvt",
    #     output_path="files/my_downloaded_file.rvt"
    # )