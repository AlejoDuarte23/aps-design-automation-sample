"""
Example 1 JSON: Complete Workflow with JSON Parameters
This example shows the FULL workflow when starting fresh with JSON parameter support:
1. Create a new bucket
2. Upload AppBundle
3. Create AppBundle alias
4. Create Activity (with JSON parameter support)
5. Create Activity alias
6. Run workitem (with JSON cube parameters)
7. Download result

This example specifically works with the CubeApp which expects a JSON parameter
with cube dimensions: {"lengthMeters": 3.0}
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
    create_activity_json,
    create_activity_alias,
    get_nickname,
)
from dotenv import load_dotenv
from typing import Annotated, Literal

load_dotenv()

# Get credentials
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REGION = "US"


def run_complete_json_workflow(
    appbundle_id: Annotated[str, "Name of the AppBundle"],
    appbundle_zip_path: Annotated[str, "Path to the zip file"],
    activity_id: Annotated[str, "Name of the Activity"],
    alias: Annotated[str, "Version alias like <test>, <dev>, <prod>"],
    input_file_path: Annotated[str, "Path to input Revit file"],
    cube_length_meters: Annotated[float, "Length of the cube in meters"],
    engine: Literal[
        "Autodesk.Revit+2023", "Autodesk.Revit+2024", "Autodesk.Revit+2025"
    ],
):
    """
    Complete workflow from scratch with JSON parameter support

    Args:
        appbundle_id: Name for the AppBundle (e.g., "CreateCubeApp")
        appbundle_zip_path: Path to AppBundle zip file (e.g., "files/MyRevitAddin.bundle.zip")
        activity_id: Name for the Activity (e.g., "CreateCubeActivity")
        alias: Version alias (e.g., "test", "dev", "prod", "staging")
        input_file_path: Path to input Revit file (e.g., "files/DeleteWalls.rvt")
        cube_length_meters: Length of the cube to create in meters (e.g., 3.0, 5.5)
        engine: Revit engine version (e.g., "Autodesk.Revit+2024")

    Returns:
        Dictionary with bucket_key, appbundle_id, activity_id, alias, and workitem_result
    """

    # Generate unique bucket key (must be lowercase, alphanumeric)
    unique_id = str(uuid.uuid4()).replace("-", "")[:16]
    new_bucket_key = f"revitbucket{unique_id}".lower()

    print("\n" + "=" * 80)
    print(f"CONFIGURATION: {activity_id} with JSON Parameters")
    print("=" * 80)
    print(f"AppBundle: {appbundle_id} | Activity: {activity_id} | Alias: {alias}")
    print(f"Engine: {engine} | Bucket: {new_bucket_key}")
    print(f"Cube Length: {cube_length_meters} meters")

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
            description=f"AppBundle for {appbundle_id} - creates cubes with JSON parameters",
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
    print("STEP 3: CREATE ACTIVITY WITH JSON SUPPORT")
    print("=" * 80)

    try:
        # Get nickname for creating full AppBundle alias
        nickname = get_nickname(token)
        appbundle_full_alias = f"{nickname}.{appbundle_id}+{alias}"
        
        # Create Activity with JSON parameter support
        create_activity_json(
            activity_id=activity_id,
            engine=engine,
            appbundle_full_alias=appbundle_full_alias,
            description=f"Activity for {activity_id} - creates cubes with JSON parameters",
            token=token,
            input_local_name="input.rvt",
            result_local_name="result.rvt",
            json_param_name="cubeParams",  # Must match the parameter name in C# code
            json_local_name="cube.json",   # Must match JsonLocalName in C# code
        )
        
        # Create alias for Activity
        create_activity_alias(
            activity_id=activity_id, alias_id=alias, version=1, token=token
        )
        
        full_activity_alias = f"{nickname}.{activity_id}+{alias}"
        print(f"Activity created: {full_activity_alias}")

    except Exception as e:
        if "409" in str(e) or "conflict" in str(e).lower():
            print("Warning: Activity already exists, continuing...")
        else:
            print(f"Error creating Activity: {e}")
            raise

    print("\n" + "=" * 80)
    print("STEP 4: RUN WORKITEM WITH JSON PARAMETERS")
    print("=" * 80)

    if not os.path.exists(input_file_path):
        print(f"Error: Input file not found: {input_file_path}")
        return

    # Create cube parameters JSON that matches the C# CubeParams class
    cube_params = {
        "lengthMeters": cube_length_meters
    }
    
    print(f"Cube parameters: {cube_params}")

    # Initialize workflow with the new bucket
    workflow = DesignAutomationWorkflow(bucket_key=new_bucket_key)

    # Run workitem with JSON parameters
    workitem_result = workflow.run_workitem_with_json(
        input_file_path=input_file_path,
        activity_id=activity_id,
        alias=alias,
        json_params=cube_params,
        json_param_name="cubeParams",  # Must match the parameter name
        max_wait_time=300,  # Wait up to 5 minutes
        poll_interval=10,   # Check status every 10 seconds
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
        print(f"  Cube Length: {cube_length_meters} meters")
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
        "cube_params": cube_params,
        "workitem_result": workitem_result,
    }


if __name__ == "__main__":
    """
    Run the complete JSON workflow with your specific parameters
    """

    result = run_complete_json_workflow(
        appbundle_id="CreateCubeApp",
        appbundle_zip_path="files/MyRevitAddin.bundle.zip",
        activity_id="CreateCubeActivity",
        alias="prod",
        input_file_path="files/DeleteWalls.rvt",
        cube_length_meters=435.0,  # Create a 5-meter cube
        engine="Autodesk.Revit+2024",
    )

    # You can save the result for later use
    if result and result["workitem_result"]["status"] == "success":
        print(f"\n💡 Save bucket for future runs: {result['bucket_key']}")
        print("Tip: Use Example 2 to run more workitems with existing resources")
        print(f"Tip: Cube created with {result['cube_params']['lengthMeters']} meter dimensions")