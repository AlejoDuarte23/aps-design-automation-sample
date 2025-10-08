import os
import json
import requests
from typing import Dict, Any, Optional, Annotated
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

APS_BASE_URL = "https://developer.api.autodesk.com"
OSS_V2_BASE_URL = f"{APS_BASE_URL}/oss/v2"
OSS_V4_BASE_URL = f"{APS_BASE_URL}/oss/v4"
MD_BASE_URL = f"{APS_BASE_URL}/modelderivative/v2"
DA_BASE_URL = f"{APS_BASE_URL}/da/us-east/v3"
AUTH_URL = f"{APS_BASE_URL}/authentication/v2/token"
SCOPES = "data:read data:write data:create bucket:create bucket:read code:all"

# Get client and secret from env
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")


def _auth_header(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@lru_cache(maxsize=1)
def get_token(client_id: str, client_secret: str) -> str:
    response = requests.post(
        AUTH_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
            "scope": SCOPES,
        },
        timeout=15,
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    return token


def register_appbundle(
    app_id: str, engine: str, description: str, token: str
) -> tuple[Annotated[str | None, "EndpointUrl"], Annotated[dict | None, "FormData"]]:
    """
    Create a new AppBundle definition and receive S3 upload parameters for version 1.
    Returns the response JSON which contains uploadParameters.
    """
    url = f"{DA_BASE_URL}/appbundles"
    payload = {"id": app_id, "engine": engine, "description": description}
    r = requests.post(
        url,
        headers={**_auth_header(token), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    upload_parameters = r.json()
    # endpoint = upload_parameters["uploadParameters"]["endpointURL"]
    upload_data = upload_parameters.get("uploadParameters", {})
    endpoint, form = upload_data.get("endpointURL"), upload_data.get("formData")
    return endpoint, form


def upload_appbundle_zip(endpoint: str, form: dict, zip_path: str) -> int:
    """
    Upload the AppBundle zip to the presigned S3 endpoint returned by register or version create.
    Returns the HTTP status code from S3, 200 indicates success.
    """
    with open(zip_path, "rb") as f:
        # Create a copy of form data and add the file
        files = {**form, 'file': (os.path.basename(zip_path), f, "application/octet-stream")}
        r = requests.post(endpoint, files=files, timeout=60)
    r.raise_for_status()
    return r.status_code


def create_appbundle_alias(
    app_id: str, alias_id: str, version: int, token: str
) -> Dict[str, Any]:
    """
    Create an alias for an AppBundle version.
    """
    url = f"{DA_BASE_URL}/appbundles/{app_id}/aliases"
    payload = {"version": version, "id": alias_id}
    r = requests.post(
        url,
        headers={**_auth_header(token), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def create_appbundle_version(
    app_id: str, engine: str, description: str, token: str
) -> Dict[str, Any]:
    """
    Create a new version of an existing AppBundle and receive S3 upload parameters.
    Returns the response JSON which contains uploadParameters and the new version number.
    """
    url = f"{DA_BASE_URL}/appbundles/{app_id}/versions"
    payload = {"id": None, "engine": engine, "description": description}
    r = requests.post(
        url,
        headers={**_auth_header(token), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def get_nickname(token: str) -> str:
    """
    Get the nickname (owner/qualifier) for the current APS account.
    This is the prefix used for AppBundles and Activities.
    Returns the nickname string directly.
    """
    url = f"{DA_BASE_URL}/forgeapps/me"
    r = requests.get(
        url,
        headers=_auth_header(token),
        timeout=30,
    )
    r.raise_for_status()
    # The API returns just a string (the nickname) as plain text, not JSON
    # Example response: "NlcIXVPn3lsQ5uGD5NDyRPG5B747Syd0EPyQPNDgCkzoZy1G"
    return r.text.strip().strip('"')  # Remove quotes if present


def create_nickname(nickname: str, token: str) -> str:
    """
    Create/set a nickname (owner/qualifier) for the current APS account.
    This is the prefix that will be used for all your AppBundles and Activities.
    Returns the created nickname.
    """
    url = f"{DA_BASE_URL}/forgeapps/me"
    r = requests.patch(
        url,
        headers={**_auth_header(token), "Content-Type": "application/json"},
        json=nickname,  # Send the nickname string directly as JSON
        timeout=30,
    )
    r.raise_for_status()
    # The API returns the nickname string
    return r.text.strip().strip('"')


def _short_appbundle_id(appbundle_full_alias: str) -> str:
    """
    Extract the short AppBundle id used inside $(appbundles[SHORT].path)
    Example input: 'myNick.DeleteWallsApp+test' -> 'DeleteWallsApp'
    """
    right = appbundle_full_alias.split(".", 1)[-1]
    return right.split("+", 1)[0]


def create_activity(
    activity_id: str,
    engine: str,
    appbundle_full_alias: str,
    description: str,
    token: str,
    input_local_name: str = "input.rvt",
    result_local_name: str = "result.rvt",
) -> Dict[str, Any]:
    """
    Create a Revit based Activity that runs an AppBundle.
    appbundle_full_alias looks like '<NICK>.DeleteWallsApp+test'
    """
    short_id = _short_appbundle_id(appbundle_full_alias)
    command = (
        f"$(engine.path)\\revitcoreconsole.exe "
        f'/i "$(args[rvtFile].path)" '
        f'/al "$(appbundles[{short_id}].path)"'
    )

    payload = {
        "id": activity_id,
        "commandLine": [command],
        "parameters": {
            "rvtFile": {
                "zip": False,
                "ondemand": False,
                "verb": "get",
                "description": "Input Revit model",
                "required": True,
                "localName": input_local_name,
            },
            "result": {
                "zip": False,
                "ondemand": False,
                "verb": "put",
                "description": "Results",
                "required": True,
                "localName": result_local_name,
            },
        },
        "engine": engine,
        "appbundles": [appbundle_full_alias],
        "description": description,
    }

    url = f"{DA_BASE_URL}/activities"
    r = requests.post(
        url,
        headers={**_auth_header(token), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def create_activity_alias(
    activity_id: str, alias_id: str, version: int, token: str
) -> Dict[str, Any]:
    """
    Create an alias for an Activity version.
    """
    url = f"{DA_BASE_URL}/activities/{activity_id}/aliases"
    payload = {"version": version, "id": alias_id}
    r = requests.post(
        url,
        headers={**_auth_header(token), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def create_bucket(
    bucket_key: str,
    token: str,
    policy_key: str = "transient",
    access: str = "full",
    region: str = "US",
) -> Dict[str, Any]:
    """
    Create a bucket in OSS v2.
    policy_key can be transient, temporary, or persistent.
    """
    url = f"{OSS_V2_BASE_URL}/buckets"
    payload = {"bucketKey": bucket_key, "access": access, "policyKey": policy_key}
    headers = {
        **_auth_header(token),
        "Content-Type": "application/json",
        "x-ads-region": region,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def get_signed_s3_upload(
    bucket_key: str, object_key: str, token: str
) -> tuple[str, str]:
    """
    Get a signed S3 upload URL and uploadKey for a single part upload.
    Returns a tuple of (signed_url, upload_key).
    """
    url = f"{OSS_V2_BASE_URL}/buckets/{bucket_key}/objects/{object_key}/signeds3upload"
    r = requests.get(url, headers=_auth_header(token), timeout=30)
    r.raise_for_status()
    response = r.json()
    
    # Extract the signed URL (first URL in the list) and upload key
    signed_url = response.get('urls', [None])[0]
    upload_key = response.get('uploadKey')
    
    return signed_url, upload_key


def put_to_signed_url(signed_url: str, file_path: str) -> int:
    """
    Upload a file to the given signed URL with a single PUT.
    Returns the HTTP status code, 200 or 201 indicates success.
    """
    with open(file_path, "rb") as f:
        r = requests.put(
            signed_url,
            data=f,
            headers={"Content-Type": "application/octet-stream"},
            timeout=120,
        )
    r.raise_for_status()
    return r.status_code


def complete_signed_s3_upload(
    bucket_key: str, object_key: str, upload_key: str, token: str
) -> Dict[str, Any]:
    """
    Complete the signed S3 upload and create the OSS object.
    """
    url = f"{OSS_V2_BASE_URL}/buckets/{bucket_key}/objects/{object_key}/signeds3upload"
    payload = {"uploadKey": upload_key}
    r = requests.post(
        url,
        headers={**_auth_header(token), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def build_oss_urn(bucket_key: str, object_key: str) -> str:
    """
    Build an OSS URN for use in Design Automation arguments.
    """
    return f"urn:adsk.objects:os.object:{bucket_key}/{object_key}"


def get_signed_s3_download(
    bucket_key: str, object_key: str, token: str
) -> Dict[str, Any]:
    """
    Get a signed S3 download URL for an OSS object.
    """
    url = (
        f"{OSS_V2_BASE_URL}/buckets/{bucket_key}/objects/{object_key}/signeds3download"
    )
    r = requests.get(url, headers=_auth_header(token), timeout=30)
    r.raise_for_status()
    return r.json()


def download_from_signed_url(signed_url: str, output_path: str) -> int:
    """
    Download a file from a signed URL to a local path.
    Returns the HTTP status code, 200 indicates success.
    """
    r = requests.get(signed_url, timeout=120)
    r.raise_for_status()
    
    # Write the content to file
    with open(output_path, "wb") as f:
        f.write(r.content)
    
    return r.status_code


def download_oss_object(
    bucket_key: str, object_key: str, output_path: str, token: str
) -> str:
    """
    Complete workflow to download an OSS object to a local file.
    Returns the local file path.
    """
    # Get signed download URL
    response = get_signed_s3_download(bucket_key, object_key, token)
    signed_url = response.get("url")
    
    if not signed_url:
        raise ValueError("No signed URL in response")
    
    # Download the file
    download_from_signed_url(signed_url, output_path)
    
    return output_path

# -------- WorkItems --------

def create_workitem_for_revit(
    activity_full_alias: str,
    input_oss_urn: str,
    result_oss_urn: str,
    token: str,
    embedded_json_param: Optional[str] = None,
    embedded_json_value: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Create a WorkItem for a Revit Activity with a model input and a model result.
    Optionally embed a JSON parameter using a data URL, provide both the parameter name and the dict value.
    """
    arguments: Dict[str, Any] = {
        "rvtFile": {
            "url": input_oss_urn,
            "verb": "get",
            "headers": {"Authorization": f"Bearer {token}"},
        },
        "result": {
            "url": result_oss_urn,
            "verb": "put",
            "headers": {"Authorization": f"Bearer {token}"},
        },
    }

    if embedded_json_param and embedded_json_value is not None:
        data_str = json.dumps(embedded_json_value, separators=(",", ":"))
        arguments[embedded_json_param] = {"url": f"data:application/json,{data_str}"}

    payload = {"activityId": activity_full_alias, "arguments": arguments}
    url = f"{DA_BASE_URL}/workitems"
    r = requests.post(
        url,
        headers={**_auth_header(token), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def get_workitem_status(workitem_id: str, token: str) -> Dict[str, Any]:
    """
    Get the current status and report URL for a WorkItem.
    """
    url = f"{DA_BASE_URL}/workitems/{workitem_id}"
    r = requests.get(
        url,
        headers={**_auth_header(token), "Content-Type": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def create_activity_json(
    activity_id: str,
    engine: str,
    appbundle_full_alias: str,
    description: str,
    token: str,
    input_local_name: str = "input.rvt",
    result_local_name: str = "result.rvt",
    json_param_name: str = "cubeParams",
    json_local_name: str = "cube.json",
) -> Dict[str, Any]:
    """
    Create a Revit Activity that runs an AppBundle and accepts a JSON parameter saved as json_local_name.
    """
    short_id = _short_appbundle_id(appbundle_full_alias)
    command = (
        f"$(engine.path)\\revitcoreconsole.exe "
        f'/i "$(args[rvtFile].path)" '
        f'/al "$(appbundles[{short_id}].path)"'
    )

    payload = {
        "id": activity_id,
        "commandLine": [command],
        "parameters": {
            "rvtFile": {
                "zip": False,
                "ondemand": False,
                "verb": "get",
                "description": "Input Revit model",
                "required": True,
                "localName": input_local_name,
            },
            json_param_name: {
                "zip": False,
                "ondemand": False,
                "verb": "get",
                "description": "Cube parameters JSON",
                "required": False,
                "localName": json_local_name,
            },
            "result": {
                "zip": False,
                "ondemand": False,
                "verb": "put",
                "description": "Results",
                "required": True,
                "localName": result_local_name,
            },
        },
        "engine": engine,
        "appbundles": [appbundle_full_alias],
        "description": description,
    }

    url = f"{DA_BASE_URL}/activities"
    r = requests.post(
        url,
        headers={**_auth_header(token), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def create_build_structure_activity(
    activity_id: str,
    engine: str,
    appbundle_full_alias: str,
    description: str,
    token: str,
    input_local_name: str = "input.rvt",
    json_param_name: str = "structure",
    json_local_name: str = "structure.json",
    result_local_name: str = "result.rvt",
) -> dict:
    """
    Create a Revit Activity that runs an AppBundle and accepts a structure JSON parameter.
    This is specifically designed for the BuildStructureApp which expects structure.json
    with connectivity nodes and lines/members definition.
    """
    short_id = _short_appbundle_id(appbundle_full_alias)
    command = (
        f"$(engine.path)\\revitcoreconsole.exe "
        f'/i "$(args[rvtFile].path)" '
        f'/al "$(appbundles[{short_id}].path)"'
    )

    payload = {
        "id": activity_id,
        "commandLine": [command],
        "parameters": {
            "rvtFile": {
                "zip": False,
                "ondemand": False,
                "verb": "get",
                "description": "Input Revit model",
                "required": True,
                "localName": input_local_name,
            },
            json_param_name: {
                "zip": False,
                "ondemand": False,
                "verb": "get",
                "description": "Structure parameters JSON",
                "required": True,
                "localName": json_local_name,
            },
            "result": {
                "zip": False,
                "ondemand": False,
                "verb": "put",
                "description": "Output Revit model",
                "required": True,
                "localName": result_local_name,
            },
        },
        "engine": engine,
        "appbundles": [appbundle_full_alias],
        "description": description,
    }

    url = f"{DA_BASE_URL}/activities"
    r = requests.post(url, headers={**_auth_header(token), "Content-Type": "application/json"}, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()
