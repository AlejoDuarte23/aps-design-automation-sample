"""
Example 3 JSON: Complete Workflow with Structure JSON Parameters
This example shows the FULL workflow when starting fresh with JSON parameter support for building structures:
1. Create a new bucket
2. Upload AppBundle
3. Create AppBundle alias
4. Create Activity (with structure JSON parameter support)
5. Create Activity alias
6. Run workitem (with structure JSON parameters)
7. Download result

This example specifically works with the BuildStructureApp which expects a JSON parameter
with structure definition including connectivity nodes and lines/members.
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
    create_build_structure_activity,
    create_activity_alias,
    get_nickname,
)
from dotenv import load_dotenv
from typing import Annotated, Literal, Dict, Any

load_dotenv()

# Get credentials
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REGION = "US"


def run_complete_structure_workflow(
    appbundle_id: Annotated[str, "Name of the AppBundle"],
    appbundle_zip_path: Annotated[str, "Path to the zip file"],
    activity_id: Annotated[str, "Name of the Activity"],
    alias: Annotated[str, "Version alias like <test>, <dev>, <prod>"],
    input_file_path: Annotated[str, "Path to input Revit file"],
    structure_params: Annotated[Dict[str, Any], "Structure parameters dictionary"],
    engine: Literal[
        "Autodesk.Revit+2023", "Autodesk.Revit+2024", "Autodesk.Revit+2025"
    ],
):
    """
    Complete workflow from scratch with structure JSON parameter support

    Args:
        appbundle_id: Name for the AppBundle (e.g., "BuildStructureApp")
        appbundle_zip_path: Path to AppBundle zip file (e.g., "files/MyRevitAddin.bundle.zip")
        activity_id: Name for the Activity (e.g., "BuildStructureActivity")
        alias: Version alias (e.g., "test", "dev", "prod", "staging")
        input_file_path: Path to input Revit file (e.g., "files/DeleteWalls.rvt")
        structure_params: Dictionary with structure definition (connectivity, lines, units)
        engine: Revit engine version (e.g., "Autodesk.Revit+2024")

    Returns:
        Dictionary with bucket_key, appbundle_id, activity_id, alias, and workitem_result
    """

    # Generate unique bucket key (must be lowercase, alphanumeric)
    unique_id = str(uuid.uuid4()).replace("-", "")[:16]
    new_bucket_key = f"revitbucket{unique_id}".lower()

    print("\n" + "=" * 80)
    print(f"CONFIGURATION: {activity_id} with Structure JSON Parameters")
    print("=" * 80)
    print(f"AppBundle: {appbundle_id} | Activity: {activity_id} | Alias: {alias}")
    print(f"Engine: {engine} | Bucket: {new_bucket_key}")
    
    # Show structure summary
    nodes_count = len(structure_params.get("connectivity", {}))
    lines_count = len(structure_params.get("lines", {}))
    units = structure_params.get("units", "m")
    print(f"Structure: {nodes_count} nodes, {lines_count} members, units: {units}")

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
            description=f"AppBundle for {appbundle_id} - builds structures with JSON parameters",
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
    print("STEP 3: CREATE ACTIVITY WITH STRUCTURE JSON SUPPORT")
    print("=" * 80)

    try:
        # Get nickname for creating full AppBundle alias
        nickname = get_nickname(token)
        appbundle_full_alias = f"{nickname}.{appbundle_id}+{alias}"
        
        # Create Activity with structure JSON parameter support
        create_build_structure_activity(
            activity_id=activity_id,
            engine=engine,
            appbundle_full_alias=appbundle_full_alias,
            description=f"Activity for {activity_id} - builds structures with JSON parameters",
            token=token,
            input_local_name="input.rvt",
            json_param_name="structure",      # Must match the parameter name in C# code
            json_local_name="structure.json", # Must match JsonLocalName in C# code
            result_local_name="result.rvt",
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
    print("STEP 4: RUN WORKITEM WITH STRUCTURE JSON PARAMETERS")
    print("=" * 80)

    if not os.path.exists(input_file_path):
        print(f"Error: Input file not found: {input_file_path}")
        return
    
    print("Structure parameters:")
    print(f"  Units: {structure_params.get('units', 'm')}")
    print(f"  Nodes: {len(structure_params.get('connectivity', {}))}")
    print(f"  Members: {len(structure_params.get('lines', {}))}")

    # Initialize workflow with the new bucket
    workflow = DesignAutomationWorkflow(bucket_key=new_bucket_key)

    # Run workitem with structure JSON parameters
    workitem_result = workflow.run_workitem_with_json(
        input_file_path=input_file_path,
        activity_id=activity_id,
        alias=alias,
        json_params=structure_params,
        json_param_name="structure",  # Must match the parameter name
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
        print(f"  Structure: {nodes_count} nodes, {lines_count} members")
        print(f"  Units: {units}")
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
        "structure_params": structure_params,
        "workitem_result": workitem_result,
    }


def create_sample_structure():
    """
    Create a sample structure definition that matches the C# StructureInput class.
    This creates a simple rectangular frame structure.
    """
    return {
        "units": "m",
        "connectivity": {
            "1": {"x": 0.0, "y": 0.0, "z": 0.0},
            "2": {"x": 0.0, "y": 6.0, "z": 0.0},
            "3": {"x": 0.0, "y": 0.0, "z": 4.0},
            "4": {"x": 0.0, "y": 6.0, "z": 4.0},
            "5": {"x": 4.0, "y": 0.0, "z": 0.0},
            "6": {"x": 4.0, "y": 6.0, "z": 0.0},
            "7": {"x": 4.0, "y": 0.0, "z": 4.0},
            "8": {"x": 4.0, "y": 6.0, "z": 4.0}
        },
        "lines": {
            "1": {"nodeI": "1", "nodeJ": "3", "section": "UB305x165x4"},
            "2": {"nodeI": "2", "nodeJ": "4", "section": "UB305x165x4"},
            "3": {"nodeI": "5", "nodeJ": "7", "section": "UB305x165x4"},
            "4": {"nodeI": "6", "nodeJ": "8", "section": "UB305x165x4"},
            "5": {"nodeI": "3", "nodeJ": "4", "section": "UB305x165x4"},
            "6": {"nodeI": "7", "nodeJ": "8", "section": "UB305x165x4"},
            "7": {"nodeI": "3", "nodeJ": "7", "section": "UB305x165x4"},
            "8": {"nodeI": "4", "nodeJ": "8", "section": "UB305x165x4"},
            "9": {"nodeI": "1", "nodeJ": "2", "section": "UB305x165x4"},
            "10": {"nodeI": "5", "nodeJ": "6", "section": "UB305x165x4"}
        }
    }


def create_simple_structure():
    """
    Create a simple 2-column structure for testing.
    """
    return {
        "units": "m",
        "connectivity": {
            "1": {"x": 0.0, "y": 0.0, "z": 0.0},
            "2": {"x": 0.0, "y": 0.0, "z": 3.0},
            "3": {"x": 3.0, "y": 0.0, "z": 0.0},
            "4": {"x": 3.0, "y": 0.0, "z": 3.0},
        },
        "lines": {
            "1": {"nodeI": "1", "nodeJ": "2", "section": "UC254x254x73"},
            "2": {"nodeI": "3", "nodeJ": "4", "section": "UC254x254x73"},
            "3": {"nodeI": "2", "nodeJ": "4", "section": "UB305x165x4"},
        }
    }


if __name__ == "__main__":
    """
    Run the complete structure workflow with your specific parameters
    """

    # Choose your structure definition
    # structure_definition = create_simple_structure()  # Simple 2-column structure
    structure_definition = create_sample_structure()    # Full rectangular frame

    result = run_complete_structure_workflow(
        appbundle_id="BuildStructureApp",
        appbundle_zip_path="files/MyRevitAddin.bundle.zip",
        activity_id="BuildStructureActivity",
        alias="prod",
        input_file_path="files/revit_input.rvt",
        structure_params=structure_definition,
        engine="Autodesk.Revit+2024",
    )

    # You can save the result for later use
    if result and result["workitem_result"]["status"] == "success":
        print(f"\n💡 Save bucket for future runs: {result['bucket_key']}")
        print("Tip: Use this bucket to run more workitems with existing resources")
        
        structure = result["structure_params"]
        nodes_count = len(structure.get("connectivity", {}))
        lines_count = len(structure.get("lines", {}))
        print(f"Tip: Structure created with {nodes_count} nodes and {lines_count} members")