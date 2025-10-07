"""
Example 1: Complete Workflow from Scratch
This example shows the FULL workflow when starting fresh:
1. Create a new bucket
2. Upload AppBundle
3. Create AppBundle alias
4. Create Activity
5. Create Activity alias        print(f"Tip: Save bucket for future runs: {result['bucket_key']}")6. Run workitem
7. Download result
"""

import os
import sys
import uuid

# Add parent directory to path to import from main and tools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation_workflow.main import DesignAutomationWorkflow
from automation_workflow.tools import (
    get_token,
    create_bucket,
    register_appbundle,
    upload_appbundle_zip,
    create_appbundle_alias,
)
from dotenv import load_dotenv
from typing import Annotated, Literal

load_dotenv()

# Get credentials
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REGION = "US"


def run_complete_workflow(
    appbundle_id: Annotated[str, "Name of the AppBundle"],
    appbundle_zip_path: Annotated[str, "Path to the zip file"],
    activity_id: Annotated[str, "Name of the AppBundle"],
    alias: Annotated[str, "Version alias like <test>, <dev>, <prod>"],
    input_file_path: Annotated[str, "Path to input Revit file"],
    engine: Literal[
        "Autodesk.Revit+2023", "Autodesk.Revit+2024", "Autodesk.Revit+2025"
    ],
):
    """
    Complete workflow from scratch with all steps

    Args:
        appbundle_id: Name for the AppBundle (e.g., "DeleteWallsApp", "MyCustomApp")
        appbundle_zip_path: Path to AppBundle zip file (e.g., "files/DeleteWallsApp.zip")
        activity_id: Name for the Activity (e.g., "DeleteWallsActivity", "ProcessWallsActivity")
        alias: Version alias (e.g., "test", "dev", "prod", "staging")
        input_file_path: Path to input Revit file (e.g., "files/DeleteWalls.rvt", "files/MyModel.rvt")
        engine: Revit engine version (e.g., "Autodesk.Revit+2023", "Autodesk.Revit+2024", "Autodesk.Revit+2025")

    Returns:
        Dictionary with bucket_key, appbundle_id, activity_id, alias, and workitem_result
    """

    # Generate unique bucket key (must be lowercase, alphanumeric)
    unique_id = str(uuid.uuid4()).replace("-", "")[:16]
    new_bucket_key = f"revitbucket{unique_id}".lower()

    print("\n" + "=" * 80)
    print(f"CONFIGURATION: {activity_id}")
    print("=" * 80)
    print(f"AppBundle: {appbundle_id} | Activity: {activity_id} | Alias: {alias}")
    print(f"Engine: {engine} | Bucket: {new_bucket_key}")

    # Get authentication token
    token = get_token(CLIENT_ID, CLIENT_SECRET)

    print("\n" + "=" * 80)
    print("STEP 1: CREATE BUCKET")
    print("=" * 80)

    try:
        bucket_result = create_bucket(
            bucket_key=new_bucket_key,
            token=token,
            policy_key="transient",  # Options: transient (24h), temporary (30d), persistent
            access="full",  # Options: full, read
            region=REGION,
        )
        print(f"Bucket created: {new_bucket_key} ({bucket_result.get('policyKey')})")
    except Exception as e:
        if "409" in str(e) or "conflict" in str(e).lower():
            print("Warning: Bucket already exists, continuing...")
        else:
            print(f"Error creating bucket: {e}")
            raise

    print("\n" + "=" * 80)
    print("STEP 2: UPLOAD APPBUNDLE")
    print("=" * 80)

    try:
        # Register AppBundle (creates version 1)
        endpoint, form_data = register_appbundle(
            app_id=appbundle_id,
            engine=engine,
            description=f"AppBundle for {appbundle_id} - processes Revit models",
            token=token,
        )

        # Upload the zip file to S3
        if not os.path.exists(appbundle_zip_path):
            print(f"Error: File not found: {appbundle_zip_path}")
            return

        status = upload_appbundle_zip(
            endpoint=endpoint, form=form_data, zip_path=appbundle_zip_path
        )

        # Create alias for AppBundle
        alias_result = create_appbundle_alias(
            app_id=appbundle_id, alias_id=alias, version=1, token=token
        )
        print(
            f"AppBundle uploaded: {appbundle_id} v{alias_result.get('version')} ({alias})"
        )

    except Exception as e:
        if "409" in str(e) or "conflict" in str(e).lower():
            print("Warning: AppBundle already exists, continuing...")
        else:
            print(f"Error with AppBundle: {e}")
            raise

    print("\n" + "=" * 80)
    print("STEP 3: CREATE ACTIVITY")
    print("=" * 80)

    # Initialize workflow with the new bucket
    workflow = DesignAutomationWorkflow(bucket_key=new_bucket_key)

    try:
        activity_result = workflow.setup_activity(
            activity_id=activity_id, appbundle_id=appbundle_id, alias=alias
        )
        print(f"Activity created: {activity_result['full_activity_alias']}")

    except Exception as e:
        if "409" in str(e) or "conflict" in str(e).lower():
            print("Warning: Activity already exists, continuing...")
        else:
            print(f"Error creating Activity: {e}")
            raise

    print("\n" + "=" * 80)
    print("STEP 4: RUN WORKITEM")
    print("=" * 80)

    if not os.path.exists(input_file_path):
        print(f"Error: Input file not found: {input_file_path}")
        return

    workitem_result = workflow.run_workitem(
        input_file_path=input_file_path,
        activity_id=activity_id,
        alias=alias,
        max_wait_time=300,  # Wait up to 5 minutes
        poll_interval=10,  # Check status every 10 seconds
        download_result=True,  # Automatically download result
    )

    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)

    status = workitem_result["status"]
    elapsed = workitem_result["elapsed_time"]

    if status == "success":
        print(f"SUCCESS - WorkItem completed in {elapsed}s")
        print(f"  Input:  {input_file_path}")
        print(
            f"  Output: {workitem_result.get('downloaded_file_path', 'Not downloaded')}"
        )

        if "downloaded_file_size" in workitem_result:
            input_size = os.path.getsize(input_file_path)
            output_size = workitem_result["downloaded_file_size"]
            change = output_size - input_size
            print(f"  Size change: {change:+,} bytes")

    elif status == "failed":
        print(f"FAILED - Check report: {workitem_result.get('report_url', 'N/A')}")

    elif status == "timeout":
        print(f"TIMEOUT - Didn't complete within {elapsed}s (increase max_wait_time)")

    print("=" * 80)

    # Return results for further use
    return {
        "bucket_key": new_bucket_key,
        "appbundle_id": appbundle_id,
        "activity_id": activity_id,
        "alias": alias,
        "workitem_result": workitem_result,
    }


if __name__ == "__main__":
    """
    Run the complete workflow with your specific parameters
    """

    result = run_complete_workflow(
        appbundle_id="DeleteWallsApp",
        appbundle_zip_path="files/DeleteWallsApp.zip",
        activity_id="DeleteWallsActivity",
        alias="prod",
        input_file_path="files/DeleteWalls.rvt",
        engine="Autodesk.Revit+2024",
    )

    # You can save the result for later use
    if result and result["workitem_result"]["status"] == "success":
        print(f"\n💡 Save bucket for future runs: {result['bucket_key']}")
        print("Tip: Use Example 2 to run more workitems with existing resources")