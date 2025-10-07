# APS Design Automation Workflows in python

Complete workflow implementation for Autodesk Platform Services (APS) Design Automation API. This is a Python implementation of the official tutorial: https://aps.autodesk.com/en/docs/design-automation/v3/tutorials/revit/about_this_tutorial

## Prerequisites

1. APS Application credentials (Client ID & Secret)
2. Python 3.8+
3. Required packages: `pip install requests python-dotenv`

## Environment Setup

Create a `.env` file in the project root:

```env
CLIENT_ID=your_client_id_here
CLIENT_SECRET=your_client_secret_here
```
## Download Files

The following files need to be downloaded to run the example. Create a folder named `files` in the root of the repo:

- [Delete all wall bundle](https://github.com/autodesk-platform-services/aps-tutorial-postman/blob/f8469f1bf0a5dd53e8e7193c0e5a1f1e0604c3d6/DA4Revit/walkthrough_data/DeleteWallsApp.zip)
- [Revit file](https://github.com/autodesk-platform-services/aps-tutorial-postman/blob/f8469f1bf0a5dd53e8e7193c0e5a1f1e0604c3d6/DA4Revit/walkthrough_data/DeleteWalls.rvt)

## JSON Parameters

For apps that need custom parameters, use JSON communication. The JSON parameter name must match your C# Activity definition, and the JSON structure must match your C# data contract.

**Reference**: [APS Documentation - JSON Parameters](https://aps.autodesk.com/en/docs/design-automation/v3/tutorials/revit/step7-post-workitem/#additional-notes)

### Parameter Matching Between Python and C# DLL:

**Activity Definition** (must match parameter names):
```python
# Python creates Activity with parameter "cubeParams"
create_activity_json(json_param_name="cubeParams", json_local_name="cube.json")
```

**C# DLL reads the file**:
```csharp
// C# reads "cube.json" file and deserializes to CubeParams class
private const string JsonLocalName = "cube.json";

[DataContract]
private class CubeParams {
    [DataMember(Name = "lengthMeters")]  // Must match JSON key
    public double LengthMeters { get; set; }
}
```

**Python sends matching JSON**:
```python
cube_params = {"lengthMeters": 5.0}  # Key matches C# DataMember
```

### HTTP Request Example:
```json
{
  "activityId": "YourNick.CreateCubeActivity+prod",
  "arguments": {
    "rvtFile": {
      "url": "urn:adsk.objects:os.object:bucket/input.rvt"
    },
    "cubeParams": {
      "url": "data:application/json,{\"lengthMeters\": 5.0}"
    },
    "result": {
      "verb": "put", 
      "url": "urn:adsk.objects:os.object:bucket/result.rvt"
    }
  }
}
```

See `example_1_json_workflow.py` for complete implementation.