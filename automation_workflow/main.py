import os
import time
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from automation_workflow.tools import (
    get_token, get_nickname, create_nickname, 
    create_activity, create_activity_alias,
    get_signed_s3_upload, put_to_signed_url, complete_signed_s3_upload,
    build_oss_urn, create_workitem_for_revit, get_workitem_status,
    download_oss_object
)
import uuid

load_dotenv()

# Configuration
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
ENGINE = "Autodesk.Revit+2024"


class DesignAutomationWorkflow:
    """Wrapper class for Design Automation workflow"""
    
    def __init__(self, bucket_key: str):
        """Initialize the workflow with bucket and credentials"""
        self.bucket_key = bucket_key
        self.token = get_token(CLIENT_ID, CLIENT_SECRET)
        self.nickname = None
        
    def get_or_create_nickname(self) -> str:
        """Get existing nickname or create a new one"""
        if self.nickname:
            return self.nickname
            
        try:
            self.nickname = get_nickname(self.token)
            print(f"Nickname: {self.nickname}")
        except Exception as e:
            if "404" in str(e):
                new_nickname = f"user_{str(uuid.uuid4()).replace('-', '')[:20]}"
                self.nickname = create_nickname(new_nickname, self.token)
                print(f"Nickname created: {self.nickname}")
            else:
                raise
        
        return self.nickname
    
    def setup_activity(
        self, 
        activity_id: str,
        appbundle_id: str = "DeleteWallsApp",
        alias: str = "test"
    ) -> Dict[str, Any]:
        """
        Complete setup: Create Activity and alias
        
        Args:
            activity_id: Name for the activity
            appbundle_id: Name of the AppBundle to use
            alias: Alias name for the activity
            
        Returns:
            Dictionary with activity details
        """
        print("\n" + "=" * 60)
        print("DESIGN AUTOMATION SETUP")
        print("=" * 60)
        
        # Get nickname
        nickname = self.get_or_create_nickname()
        
        # Build full AppBundle alias
        appbundle_full_alias = f"{nickname}.{appbundle_id}+{alias}"
        
        # Create Activity
        activity_result = create_activity(
            activity_id=activity_id,
            engine=ENGINE,
            appbundle_full_alias=appbundle_full_alias,
            description=f"Activity to process Revit models using {appbundle_id}",
            token=self.token
        )
        
        # Create Activity alias
        create_activity_alias(
            activity_id=activity_id,
            alias_id=alias,
            version=1,
            token=self.token
        )
        
        full_activity_alias = f"{activity_result.get('id')}+{alias}"
        print(f"Activity: {full_activity_alias} | AppBundle: {appbundle_full_alias}")
        
        result = {
            "nickname": nickname,
            "activity_id": activity_result.get('id'),
            "activity_version": activity_result.get('version'),
            "alias": alias,
            "full_activity_alias": full_activity_alias,
            "appbundle_alias": appbundle_full_alias
        }
        
        print("=" * 60)
        
        return result
    
    def upload_input_file(self, file_path: str) -> Tuple[str, str]:
        """
        Upload an input file to OSS
        
        Args:
            file_path: Local path to the file
            
        Returns:
            Tuple of (object_key, oss_urn)
        """
        object_key = f"input_{uuid.uuid4()}.rvt"
        
        # Get signed URL
        signed_url, upload_key = get_signed_s3_upload(
            self.bucket_key, object_key, self.token
        )
        
        # Upload file
        put_to_signed_url(signed_url, file_path)
        
        # Complete upload
        complete_signed_s3_upload(
            self.bucket_key, object_key, upload_key, self.token
        )
        
        oss_urn = build_oss_urn(self.bucket_key, object_key)
        print(f"Uploaded: {file_path} → {object_key}")
        
        return object_key, oss_urn
    
    def run_workitem(
        self,
        input_file_path: str,
        activity_id: str = "DeleteWallsActivity",
        alias: str = "test",
        max_wait_time: int = 300,
        poll_interval: int = 10,
        download_result: bool = True
    ) -> Dict[str, Any]:
        """
        Complete workflow: Upload input, run workitem, monitor, and download result
        
        Args:
            input_file_path: Local path to input Revit file
            activity_id: Activity name to use
            alias: Activity alias
            max_wait_time: Maximum seconds to wait for completion
            poll_interval: Seconds between status checks
            download_result: Whether to download the result file
            
        Returns:
            Dictionary with workitem results
        """
        print("\n" + "=" * 60)
        print("DESIGN AUTOMATION WORKITEM EXECUTION")
        print("=" * 60)
        
        # Get nickname
        nickname = self.get_or_create_nickname()
        activity_full_alias = f"{nickname}.{activity_id}+{alias}"
        
        print(f"Activity: {activity_full_alias}")
        
        # Step 1: Upload input file
        input_object_key, input_oss_urn = self.upload_input_file(input_file_path)
        
        # Step 2: Create output placeholder
        output_object_key = f"result_{uuid.uuid4()}.rvt"
        result_oss_urn = build_oss_urn(self.bucket_key, output_object_key)
        
        # Step 3: Create workitem
        workitem_response = create_workitem_for_revit(
            activity_full_alias=activity_full_alias,
            input_oss_urn=input_oss_urn,
            result_oss_urn=result_oss_urn,
            token=self.token
        )
        print(workitem_response)
        workitem_id = workitem_response.get('id')
        print(f"WorkItem submitted: {workitem_id}")
        
        # Step 4: Monitor workitem
        print("Monitoring status...")
        elapsed_time = 0
        status_response = None
        
        while elapsed_time < max_wait_time:
            status_response = get_workitem_status(workitem_id, self.token)
            print(f"{status_response=}")
            status = status_response.get('status')
            
            print(f"  [{elapsed_time:3d}s] {status}")
            
            if status in ['success', 'failed', 'cancelled']:
                break
            
            time.sleep(poll_interval)
            elapsed_time += poll_interval
        else:
            print(f"Warning: Timeout after {max_wait_time}s")
            return {
                "status": "timeout",
                "workitem_id": workitem_id,
                "elapsed_time": elapsed_time
            }
        
        # Display results
        final_status = status_response.get('status')
        result = {
            "workitem_id": workitem_id,
            "status": final_status,
            "bucket_key": self.bucket_key,
            "input_object_key": input_object_key,
            "output_object_key": output_object_key,
            "input_urn": input_oss_urn,
            "output_urn": result_oss_urn,
            "elapsed_time": elapsed_time,
            "report_url": status_response.get('reportUrl'),
            "stats": status_response.get('stats', {})
        }
        
        if final_status == 'success':
            print(f"SUCCESS - Completed in {elapsed_time}s")
            
            # Step 5: Download result
            if download_result:
                output_file_path = f"files/downloaded_{output_object_key}"
                
                try:
                    download_oss_object(
                        self.bucket_key, output_object_key, 
                        output_file_path, self.token
                    )
                    file_size = os.path.getsize(output_file_path)
                    print(f"Downloaded: {output_file_path} ({file_size:,} bytes)")
                    result['downloaded_file_path'] = output_file_path
                    result['downloaded_file_size'] = file_size
                except Exception as e:
                    print(f"Download failed: {e}")
                    result['download_error'] = str(e)
        
        elif final_status == 'failed':
            print(f"FAILED - Report: {status_response.get('reportUrl')}")
        
        print("\n" + "=" * 60)
        
        return result
    
    def run_workitem_with_json(
        self,
        input_file_path: str,
        activity_id: str = "CreateCubeActivity",
        alias: str = "test",
        json_params: Dict[str, Any] = None,
        json_param_name: str = "cubeParams",
        max_wait_time: int = 300,
        poll_interval: int = 10,
        download_result: bool = True
    ) -> Dict[str, Any]:
        """
        Complete workflow: Upload input, run workitem with JSON parameters, monitor, and download result
        
        Args:
            input_file_path: Local path to input Revit file
            activity_id: Activity name to use
            alias: Activity alias
            json_params: Dictionary to send as JSON parameter
            json_param_name: Name of the JSON parameter in the activity
            max_wait_time: Maximum seconds to wait for completion
            poll_interval: Seconds between status checks
            download_result: Whether to download the result file
            
        Returns:
            Dictionary with workitem results
        """
        print("\n" + "=" * 60)
        print("DESIGN AUTOMATION WORKITEM EXECUTION (WITH JSON)")
        print("=" * 60)
        
        # Get nickname
        nickname = self.get_or_create_nickname()
        activity_full_alias = f"{nickname}.{activity_id}+{alias}"
        
        print(f"Activity: {activity_full_alias}")
        print(f"JSON Parameter: {json_param_name} = {json_params}")
        
        # Step 1: Upload input file
        input_object_key, input_oss_urn = self.upload_input_file(input_file_path)
        
        # Step 2: Create output placeholder
        output_object_key = f"result_{uuid.uuid4()}.rvt"
        result_oss_urn = build_oss_urn(self.bucket_key, output_object_key)
        
        # Step 3: Create workitem with JSON parameters
        workitem_response = create_workitem_for_revit(
            activity_full_alias=activity_full_alias,
            input_oss_urn=input_oss_urn,
            result_oss_urn=result_oss_urn,
            token=self.token,
            embedded_json_param=json_param_name,
            embedded_json_value=json_params or {}
        )
        print(workitem_response)
        workitem_id = workitem_response.get('id')
        print(f"WorkItem submitted: {workitem_id}")
        
        # Step 4: Monitor workitem
        print("Monitoring status...")
        elapsed_time = 0
        status_response = None
        
        while elapsed_time < max_wait_time:
            status_response = get_workitem_status(workitem_id, self.token)
            print(f"{status_response=}")
            status = status_response.get('status')
            
            print(f"  [{elapsed_time:3d}s] {status}")
            
            if status in ['success', 'failed', 'cancelled']:
                break
            
            time.sleep(poll_interval)
            elapsed_time += poll_interval
        else:
            print(f"Warning: Timeout after {max_wait_time}s")
            return {
                "status": "timeout",
                "workitem_id": workitem_id,
                "elapsed_time": elapsed_time
            }
        
        # Display results
        final_status = status_response.get('status')
        result = {
            "workitem_id": workitem_id,
            "status": final_status,
            "bucket_key": self.bucket_key,
            "input_object_key": input_object_key,
            "output_object_key": output_object_key,
            "input_urn": input_oss_urn,
            "output_urn": result_oss_urn,
            "elapsed_time": elapsed_time,
            "report_url": status_response.get('reportUrl'),
            "stats": status_response.get('stats', {}),
            "json_params": json_params
        }
        
        if final_status == 'success':
            print(f"SUCCESS - Completed in {elapsed_time}s")
            
            # Step 5: Download result
            if download_result:
                output_file_path = f"files/downloaded_{output_object_key}"
                
                try:
                    download_oss_object(
                        self.bucket_key, output_object_key, 
                        output_file_path, self.token
                    )
                    file_size = os.path.getsize(output_file_path)
                    print(f"Downloaded: {output_file_path} ({file_size:,} bytes)")
                    result['downloaded_file_path'] = output_file_path
                    result['downloaded_file_size'] = file_size
                except Exception as e:
                    print(f"Download failed: {e}")
                    result['download_error'] = str(e)
        
        elif final_status == 'failed':
            print(f"FAILED - Report: {status_response.get('reportUrl')}")
        
        print("\n" + "=" * 60)
        
        return result
    
    def download_result_file(
        self, 
        object_key: str, 
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Download a specific result file from OSS
        
        Args:
            object_key: The OSS object key to download
            output_path: Optional local path (defaults to files/downloaded_{object_key})
            
        Returns:
            Dictionary with file_path and file_size
        """
        if output_path is None:
            output_path = f"files/downloaded_{object_key}"
        
        download_oss_object(self.bucket_key, object_key, output_path, self.token)
        
        file_size = os.path.getsize(output_path)
        print(f"Downloaded: {output_path} ({file_size:,} bytes)")
        
        return {
            "file_path": output_path,
            "file_size": file_size
        }
